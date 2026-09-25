#!/usr/bin/env python3
"""
World-class-at-₹0 training pipeline.

Upgrades:
  - Larger multivariate synthetic set
  - Expanded feature set (India quant + interaction features)
  - Ensemble L2 (bagged logistic / ridge)
  - Stronger L3 embeddings (more epochs, hard negatives)
  - Sequence MLP with more series + synthetic GBM
  - OCR eval on synthetic screenshots (Pillow + Tesseract)

Outputs under training/models/:
  india_l2_bundle_v2.json
  fund_embedding_v2.json
  nav_sequence_v2.json
  ocr_eval_report.json
"""
from __future__ import annotations

import json
import math
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MODELS = ROOT / "training" / "models"
REPORTS = ROOT / "training" / "reports"
SYN = ROOT / "data" / "synthetic"
RNG = random.Random(99)


def log(msg: str):
    print(msg, flush=True)


# ── Feature expansion ─────────────────────────────────────────────
BASE_FEATS = [
    "portfolio_xirr", "ter_waste_pct_aum", "overlap_waste_pct_aum", "hhi",
    "equity_pct", "regular_aum_pct", "top_sector_pct", "smallcap_pct",
    "liquid_pct", "est_tax_drag_pct_aum", "n_lots", "sip_regularity",
    "elss_locked_pct", "fd_pct", "mean_holding_years",
]


def expand_features(row: dict) -> dict:
    """Interaction features — free accuracy boost for tabular models."""
    f = {k: float(row.get(k) or 0) for k in BASE_FEATS}
    f["ter_x_regular"] = f["ter_waste_pct_aum"] * (f["regular_aum_pct"] / 100)
    f["overlap_x_hhi"] = f["overlap_waste_pct_aum"] * f["hhi"]
    f["risk_proxy"] = f["smallcap_pct"] * 0.4 + (100 - f["liquid_pct"]) * 0.3 + f["hhi"] * 50
    f["cost_drag"] = f["ter_waste_pct_aum"] + f["overlap_waste_pct_aum"] + f["est_tax_drag_pct_aum"] * 0.2
    f["quality_proxy"] = f["portfolio_xirr"] - f["cost_drag"] * 2 - f["hhi"] * 10
    f["log_n_lots"] = math.log1p(f["n_lots"])
    f["equity_x_small"] = f["equity_pct"] * f["smallcap_pct"] / 100
    return f


def load_feature_rows():
    import csv
    train = list(csv.DictReader((SYN / "features_train.csv").open()))
    val = list(csv.DictReader((SYN / "features_val.csv").open()))
    return train, val


def standardize(X):
    n_f = len(X[0])
    means, stds = [], []
    for j in range(n_f):
        col = [r[j] for r in X]
        m = sum(col) / len(col)
        v = sum((c - m) ** 2 for c in col) / max(1, len(col) - 1)
        s = math.sqrt(v) or 1.0
        means.append(m)
        stds.append(s)
    Xs = [[(r[j] - means[j]) / stds[j] for j in range(n_f)] for r in X]
    return Xs, means, stds


def apply_std(X, means, stds):
    return [[(r[j] - means[j]) / stds[j] for j in range(len(means))] for r in X]


def sigmoid(z):
    if z < -40:
        return 0.0
    if z > 40:
        return 1.0
    return 1 / (1 + math.exp(-z))


def train_logistic_bagged(X, y, bags=5, epochs=300, lr=0.05):
    models = []
    n = len(X)
    n_f = len(X[0])
    for b in range(bags):
        rng = random.Random(10 + b)
        idx = [rng.randrange(n) for _ in range(n)]
        w = [rng.uniform(-0.02, 0.02) for _ in range(n_f)]
        bias = 0.0
        for _ in range(epochs):
            for i in idx:
                z = bias + sum(w[j] * X[i][j] for j in range(n_f))
                p = sigmoid(z)
                err = p - y[i]
                for j in range(n_f):
                    w[j] -= lr * (err * X[i][j] + 0.01 * w[j])
                bias -= lr * err
        models.append({"w": w, "b": bias})
    return models


def predict_bag_log(models, x):
    ps = [sigmoid(m["b"] + sum(m["w"][j] * x[j] for j in range(len(x)))) for m in models]
    return sum(ps) / len(ps)


def train_ridge_bagged(X, y, bags=5, epochs=400, lr=0.01):
    models = []
    n = len(X)
    n_f = len(X[0])
    for b in range(bags):
        rng = random.Random(20 + b)
        idx = [rng.randrange(n) for _ in range(n)]
        w = [rng.uniform(-0.02, 0.02) for _ in range(n_f)]
        bias = 0.0
        for _ in range(epochs):
            for i in idx:
                pred = bias + sum(w[j] * X[i][j] for j in range(n_f))
                err = pred - y[i]
                for j in range(n_f):
                    w[j] -= lr * (err * X[i][j] + 0.05 * w[j])
                bias -= lr * err
        models.append({"w": w, "b": bias})
    return models


def predict_bag_ridge(models, x):
    return sum(m["b"] + sum(m["w"][j] * x[j] for j in range(len(x))) for m in models) / len(models)


def acc(y, p, thr=0.5):
    return sum(1 for yt, yp in zip(y, p) if int(yp >= thr) == yt) / max(1, len(y))


def mae(y, p):
    return sum(abs(a - b) for a, b in zip(y, p)) / max(1, len(y))


def train_l2_v2():
    log("=== L2 ensemble v2 ===")
    train, val = load_feature_rows()
    if len(train) < 200:
        raise SystemExit("Run generate_synthetic_india.py first (or full train_worldclass script)")

    ftr = [expand_features(r) for r in train]
    fva = [expand_features(r) for r in val]
    cols = list(ftr[0].keys())
    Xtr = [[f[c] for c in cols] for f in ftr]
    Xva = [[f[c] for c in cols] for f in fva]
    Xtr_s, means, stds = standardize(Xtr)
    Xva_s = apply_std(Xva, means, stds)

    tasks = {
        "has_ter_leak": ("label_has_ter_leak", "log"),
        "has_overlap": ("label_has_overlap", "log"),
        "high_concentration": ("label_high_concentration", "log"),
        "tax_heavy": ("label_tax_heavy", "log"),
        "low_liquidity": ("label_low_liquidity", "log"),
        "health_score": ("label_health_score", "ridge"),
    }
    models_out = {}
    for name, (lab, kind) in tasks.items():
        ytr = [float(r[lab]) for r in train]
        yva = [float(r[lab]) for r in val]
        if kind == "log":
            ytr_i = [int(v) for v in ytr]
            yva_i = [int(v) for v in yva]
            bags = train_logistic_bagged(Xtr_s, ytr_i, bags=7, epochs=250)
            ptr = [predict_bag_log(bags, x) for x in Xtr_s]
            pva = [predict_bag_log(bags, x) for x in Xva_s]
            metrics = {"train_acc": round(acc(ytr_i, ptr), 4), "val_acc": round(acc(yva_i, pva), 4)}
            models_out[name] = {"type": "logistic_ensemble", "bags": bags, "metrics": metrics}
        else:
            ytr_n = [v / 100 for v in ytr]
            bags = train_ridge_bagged(Xtr_s, ytr_n, bags=7, epochs=350)
            ptr = [predict_bag_ridge(bags, x) * 100 for x in Xtr_s]
            pva = [predict_bag_ridge(bags, x) * 100 for x in Xva_s]
            metrics = {"train_mae": round(mae(ytr, ptr), 3), "val_mae": round(mae(yva, pva), 3)}
            models_out[name] = {"type": "ridge_ensemble", "bags": bags, "metrics": metrics}
        log(f"  {name}: {metrics}")

    bundle = {
        "version": "india_l2_v2",
        "trained_on": "synthetic_india_expanded_features",
        "feature_columns": cols,
        "standardize": {"means": means, "stds": stds},
        "models": {
            k: {
                "type": v["type"],
                "metrics": v["metrics"],
                "bags": v["bags"],
            }
            for k, v in models_out.items()
        },
        "cost": "zero",
        "notes": "Bagged ensembles + interaction features. Free compute only.",
    }
    MODELS.mkdir(parents=True, exist_ok=True)
    # also write v1-compatible flat average weights for old loader
    compat = {
        "version": "india_l2_v2",
        "trained_on": bundle["trained_on"],
        "feature_columns": cols,
        "standardize": bundle["standardize"],
        "models": {},
        "notes": bundle["notes"],
    }
    for k, v in models_out.items():
        bags = v["bags"]
        n_f = len(bags[0]["w"])
        w_avg = [sum(b["w"][j] for b in bags) / len(bags) for j in range(n_f)]
        b_avg = sum(b["b"] for b in bags) / len(bags)
        kind = "logistic" if "logistic" in v["type"] else "ridge"
        compat["models"][k] = {
            "type": kind,
            "weights": w_avg,
            "bias": b_avg,
            "metrics": v["metrics"],
            "ensemble_bags": len(bags),
        }
    (MODELS / "india_l2_bundle.json").write_text(json.dumps(compat, indent=2))
    (MODELS / "india_l2_bundle_v2.json").write_text(
        json.dumps(
            {
                **compat,
                "full_ensemble": True,
                "bags_per_model": {k: len(v["bags"]) for k, v in models_out.items()},
            },
            indent=2,
        )
    )
    log("Saved india_l2_bundle.json (v2 weights)")
    return compat


def train_embedding_v2():
    log("=== L3 embedding v2 ===")
    # Inline BoW helpers (avoid fragile imports)
    VOCAB_SIZE, DIM = 512, 32

    def bow(name: str, category: str = "") -> list[float]:
        v = [0.0] * VOCAB_SIZE
        for t in re.split(r"[^a-z0-9]+", (name + " " + category).lower()):
            if len(t) > 1:
                v[abs(hash(t)) % VOCAB_SIZE] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def matvec(W, x, b):
        return [b[i] + sum(W[i][j] * x[j] for j in range(len(x))) for i in range(len(W))]

    def l2norm(v):
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def cosine(a, b):
        return sum(x * y for x, y in zip(a, b))

    names = []
    amfi = ROOT / "data" / "india" / "amfi_seed_funds.json"
    if amfi.exists():
        for s in json.loads(amfi.read_text()):
            if s.get("schemeName"):
                names.append((s["schemeName"], "mf"))
    if (SYN / "portfolios_train.jsonl").exists():
        for i, line in enumerate((SYN / "portfolios_train.jsonl").open()):
            if i > 1500:
                break
            try:
                doc = json.loads(line)
                for lot in doc.get("lots") or []:
                    names.append((lot.get("name") or "", lot.get("asset_class") or ""))
            except Exception:
                continue
    seen = set()
    uniq = []
    for n, c in names:
        k = n.lower().strip()
        if k and k not in seen:
            seen.add(k)
            uniq.append((n, c))
    names = uniq[:1500]
    log(f"  vocab names: {len(names)}")

    W = [[RNG.uniform(-0.05, 0.05) for _ in range(VOCAB_SIZE)] for _ in range(DIM)]
    b = [0.0] * DIM
    lr = 0.1
    for ep in range(25):
        loss = 0.0
        steps = 0
        for _ in range(min(800, len(names) * 2)):
            n1, c1 = names[RNG.randrange(len(names))]
            # hard positive: same family tokens
            n_pos = n1
            for a, rep in [("Direct", ""), ("Regular", ""), ("Fund", ""), ("  ", " ")]:
                n_pos = n_pos.replace(a, rep)
            n_neg, c_neg = names[RNG.randrange(len(names))]
            # hard negative: different name but maybe same category
            tries = 0
            while n_neg.lower() == n1.lower() and tries < 10:
                n_neg, c_neg = names[RNG.randrange(len(names))]
                tries += 1

            def emb(n, c):
                return l2norm(matvec(W, bow(n, c), b))

            e1, ep_, en = emb(n1, c1), emb(n_pos, c1), emb(n_neg, c_neg)
            pos, neg = cosine(e1, ep_), cosine(e1, en)
            # margin loss style
            x1 = bow(n1, c1)
            for d in range(DIM):
                # pull toward pos, push from neg
                delta = lr * ((ep_[d] - e1[d]) - 0.5 * en[d])
                b[d] += 0.05 * delta
                for j in range(VOCAB_SIZE):
                    if x1[j] != 0:
                        W[d][j] += delta * x1[j]
            loss += max(0, 0.2 - pos + neg)
            steps += 1
        if ep % 5 == 0:
            log(f"  epoch {ep} margin_loss~{loss/max(1,steps):.4f}")

    bundle = {
        "version": "fund_embedding_v2",
        "type": "projection_bow_hardneg",
        "dim": DIM,
        "vocab_size": VOCAB_SIZE,
        "W": W,
        "b": b,
        "layer": "L3_dl",
        "n_names_seen": len(names),
        "cost": "zero",
    }
    # write as v1 path too for loader (models.py loads fund_embedding_v1.json)
    (MODELS / "fund_embedding_v2.json").write_text(json.dumps(bundle))
    (MODELS / "fund_embedding_v1.json").write_text(json.dumps(bundle))
    log("Saved fund_embedding_v2.json (+ v1 alias)")
    return bundle


def sequence_features_local(navs: list[float]) -> list[float]:
    if len(navs) < 5:
        return [0.0] * 16
    rets = [navs[i] / navs[i - 1] - 1 for i in range(1, len(navs)) if navs[i - 1] > 0]
    if not rets:
        return [0.0] * 16
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    std = math.sqrt(var)
    peak, mdd = navs[0], 0.0
    for n in navs:
        peak = max(peak, n)
        if peak > 0:
            mdd = min(mdd, n / peak - 1)
    last = (rets[-5:] + [0] * 5)[:5]
    mom_20 = navs[-1] / navs[max(0, len(navs) - 20)] - 1 if len(navs) > 20 else 0
    mom_60 = navs[-1] / navs[max(0, len(navs) - 60)] - 1 if len(navs) > 60 else 0
    return [
        mean * 252, std * math.sqrt(252), mdd, mom_20, mom_60,
        min(rets), max(rets), last[0], last[1], last[2], last[3], last[4],
        len(rets) / 252, 1.0 if mean > 0 else 0.0, abs(mean) / (std + 1e-6),
        (navs[-1] / navs[0] - 1) if navs[0] else 0,
    ]


def train_sequence_v2():
    log("=== L3 sequence v2 ===")
    import json as _json
    import urllib.request

    def fetch_nav_series(code: str, limit: int = 150) -> list[float]:
        try:
            with urllib.request.urlopen(f"https://api.mfapi.in/mf/{code}", timeout=12) as r:
                data = _json.loads(r.read().decode())
            navs = [float(x["nav"]) for x in (data.get("data") or [])[:limit]]
            navs.reverse()
            return navs
        except Exception:
            return []

    samples = []
    # AMFI
    amfi = ROOT / "data" / "india" / "amfi_seed_funds.json"
    if amfi.exists():
        seeds = _json.loads(amfi.read_text())
        for s in seeds[:20]:
            code = str(s.get("schemeCode") or "")
            if not code:
                continue
            navs = fetch_nav_series(code, 150)
            if len(navs) > 15:
                samples.append(navs)
    for p in (ROOT / "data" / "india").glob("nav_history_sample_*.json"):
        hist = _json.loads(p.read_text())
        navs = [float(x["nav"]) for x in reversed((hist.get("data") or [])[:150])]
        if len(navs) > 15:
            samples.append(navs)
    # synthetic GBM diversity
    for _ in range(80):
        p = 100.0
        path = [p]
        mu = RNG.gauss(0.0005, 0.0003)
        sig = RNG.uniform(0.006, 0.02)
        for _d in range(120):
            p *= math.exp(RNG.gauss(mu, sig))
            path.append(p)
        samples.append(path)
    log(f"  series: {len(samples)}")

    X = [sequence_features_local(s) for s in samples]
    y_ret, y_risk = [], []
    for s in samples:
        mid = len(s) // 2
        r = s[-1] / s[mid] - 1 if mid > 0 and s[mid] else 0
        y_ret.append(max(-0.6, min(0.6, r)))
        rets = [s[i] / s[i - 1] - 1 for i in range(1, len(s)) if s[i - 1] > 0]
        std = math.sqrt(sum(x * x for x in rets) / max(1, len(rets))) if rets else 0.1
        y_risk.append(min(0.6, std * math.sqrt(252)))

    in_dim = len(X[0])
    hidden = 32
    W1 = [[RNG.uniform(-0.08, 0.08) for _ in range(in_dim)] for _ in range(hidden)]
    b1 = [0.0] * hidden
    W2 = [[RNG.uniform(-0.08, 0.08) for _ in range(hidden)] for _ in range(2)]
    b2 = [0.0, 0.0]
    lr = 0.015
    for ep in range(120):
        total = 0.0
        order = list(range(len(X)))
        RNG.shuffle(order)
        for i in order:
            h = [max(0.0, b1[k] + sum(W1[k][j] * X[i][j] for j in range(in_dim))) for k in range(hidden)]
            out = [b2[o] + sum(W2[o][k] * h[k] for k in range(hidden)) for o in range(2)]
            e0, e1 = out[0] - y_ret[i], out[1] - y_risk[i]
            total += e0 * e0 + e1 * e1
            for k in range(hidden):
                W2[0][k] -= lr * e0 * h[k]
                W2[1][k] -= lr * e1 * h[k]
            b2[0] -= lr * e0
            b2[1] -= lr * e1
            for k in range(hidden):
                if h[k] <= 0:
                    continue
                g = e0 * W2[0][k] + e1 * W2[1][k]
                b1[k] -= lr * g
                for j in range(in_dim):
                    W1[k][j] -= lr * g * X[i][j]
        if ep % 30 == 0:
            log(f"  epoch {ep} mse~{total/max(1,len(X)):.5f}")

    bundle = {
        "version": "nav_sequence_v2",
        "type": "mlp_temporal_features",
        "in_dim": in_dim,
        "hidden": hidden,
        "W1": W1,
        "b1": b1,
        "W2": W2,
        "b2": b2,
        "layer": "L3_dl",
        "n_series": len(samples),
        "outputs": ["expected_return_proxy", "risk_score"],
        "cost": "zero",
    }
    (MODELS / "nav_sequence_v2.json").write_text(json.dumps(bundle))
    (MODELS / "nav_sequence_v1.json").write_text(json.dumps(bundle))
    log("Saved nav_sequence_v2.json (+ v1 alias)")
    return bundle


def eval_ocr():
    log("=== OCR engine eval (synthetic screens) ===")
    REPORTS.mkdir(parents=True, exist_ok=True)
    try:
        from app.intelligence.ocr.synthetic_screens import random_holdings, render_portfolio_image
        from app.intelligence.ocr.engine import ocr_image_bytes, ocr_available
    except Exception as e:
        log(f"  OCR import failed: {e}")
        return {"error": str(e)}

    status = ocr_available()
    log(f"  ocr_available: {status}")
    results = []
    for i in range(12):
        holdings = random_holdings(n=RNG.randint(3, 5))
        png, plain = render_portfolio_image(holdings, title=f"Portfolio {i}")
        # Always test layout parser on ground-truth text
        from app.intelligence.ocr.layout import parse_holdings_from_ocr_text
        parsed_text = parse_holdings_from_ocr_text(plain)
        # Full image OCR if tesseract ready
        img_result = ocr_image_bytes(png)
        gt_names = {h["name"].lower()[:20] for h in holdings}
        text_names = {l["name"].lower()[:20] for l in parsed_text.get("lots") or []}
        ocr_names = {l["name"].lower()[:20] for l in img_result.get("lots") or []}
        # recall@name fuzzy
        def recall(pred, gt):
            if not gt:
                return 0.0
            hit = 0
            for g in gt:
                if any(g[:12] in p or p[:12] in g for p in pred):
                    hit += 1
            return hit / len(gt)

        results.append(
            {
                "i": i,
                "n_gt": len(holdings),
                "layout_on_plaintext_recall": round(recall(text_names, gt_names), 3),
                "full_ocr_lots": len(img_result.get("lots") or []),
                "full_ocr_recall": round(recall(ocr_names, gt_names), 3),
                "ocr_backend": img_result.get("source", {}).get("ocr_backend"),
            }
        )
    avg_layout = sum(r["layout_on_plaintext_recall"] for r in results) / len(results)
    avg_ocr = sum(r["full_ocr_recall"] for r in results) / len(results)
    report = {
        "ocr_status": status,
        "n_images": len(results),
        "avg_layout_plaintext_recall": round(avg_layout, 3),
        "avg_full_ocr_recall": round(avg_ocr, 3),
        "details": results,
        "cost": "zero",
        "stack": "Pillow preprocess → Tesseract (if present) → India layout parser → india_portfolio_v1",
    }
    (REPORTS / "ocr_eval_report.json").write_text(json.dumps(report, indent=2))
    (MODELS / "ocr_eval_report.json").write_text(json.dumps(report, indent=2))
    log(f"  layout recall={avg_layout:.3f} full_ocr_recall={avg_ocr:.3f}")
    return report


def main():
    MODELS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    # ensure synthetic data
    sys.path.insert(0, str(ROOT))
    # import generator by path
    import importlib.util
    gen_path = ROOT / "training" / "scripts" / "generate_synthetic_india.py"
    spec = importlib.util.spec_from_file_location("gen_syn", gen_path)
    gen_mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(gen_mod)
    log("Refreshing larger synthetic set (1200/300)…")
    gen_mod.main(1200, 300)

    l2 = train_l2_v2()
    emb = train_embedding_v2()
    seq = train_sequence_v2()
    ocr = eval_ocr()
    summary = {
        "l2_version": l2.get("version"),
        "l2_metrics": {k: v.get("metrics") for k, v in l2.get("models", {}).items()},
        "embedding": emb.get("version"),
        "sequence": seq.get("version"),
        "ocr": {
            "ready": (ocr.get("ocr_status") or {}).get("ready"),
            "layout_recall": ocr.get("avg_layout_plaintext_recall"),
            "ocr_recall": ocr.get("avg_full_ocr_recall"),
        },
        "cost": "₹0",
    }
    (REPORTS / "worldclass_zero_cost_summary.json").write_text(json.dumps(summary, indent=2))
    log("=== SUMMARY ===")
    log(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
