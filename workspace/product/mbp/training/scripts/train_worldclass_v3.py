#!/usr/bin/env python3
"""
World-class-at-₹0 training pipeline v3.

Upgrades over v2:
  - Larger synthetic set + v3 interaction features
  - Bagged logistic/ridge with temperature calibration
  - Stronger fund embeddings (more epochs, hard negatives, larger vocab)
  - Sequence MLP with feature-classical blend targets
  - OCR eval with layout v3 + multi-pass engine

Outputs:
  india_l2_bundle_v3.json (+ v2/v1 aliases)
  fund_embedding_v3.json (+ v2/v1 aliases)
  nav_sequence_v3.json (+ v2/v1 aliases)
  reports/worldclass_zero_cost_summary.json
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
RNG = random.Random(2026)


def log(msg: str):
    print(msg, flush=True)


from app.intelligence.ml.feature_expand import BASE_FEATS, expand_features  # noqa: E402


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


def train_logistic_bagged(X, y, bags=9, epochs=320, lr=0.05):
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
                    w[j] -= lr * (err * X[i][j] + 0.012 * w[j])
                bias -= lr * err
        models.append({"w": w, "b": bias})
    return models


def predict_bag_log(models, x):
    ps = [sigmoid(m["b"] + sum(m["w"][j] * x[j] for j in range(len(x)))) for m in models]
    return sum(ps) / len(ps)


def train_ridge_bagged(X, y, bags=9, epochs=420, lr=0.012):
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
                    w[j] -= lr * (err * X[i][j] + 0.04 * w[j])
                bias -= lr * err
        models.append({"w": w, "b": bias})
    return models


def predict_bag_ridge(models, x):
    return sum(m["b"] + sum(m["w"][j] * x[j] for j in range(len(x))) for m in models) / len(
        models
    )


def acc(y, p, thr=0.5):
    return sum(1 for yt, yp in zip(y, p) if int(yp >= thr) == yt) / max(1, len(y))


def mae(y, p):
    return sum(abs(a - b) for a, b in zip(y, p)) / max(1, len(y))


def fit_temperature(logits_or_p, y, is_prob=True):
    """Simple temperature search on validation probabilities."""
    if is_prob:
        ps = [min(max(p, 1e-6), 1 - 1e-6) for p in logits_or_p]
        logits = [math.log(p / (1 - p)) for p in ps]
    else:
        logits = logits_or_p
    best_t, best_nll = 1.0, 1e18
    for t in [0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5]:
        nll = 0.0
        for z, yt in zip(logits, y):
            p = sigmoid(z / t)
            p = min(max(p, 1e-6), 1 - 1e-6)
            nll -= yt * math.log(p) + (1 - yt) * math.log(1 - p)
        nll /= max(1, len(y))
        if nll < best_nll:
            best_nll, best_t = nll, t
    return best_t


def train_l2_v3():
    log("=== L2 ensemble v3 ===")
    train, val = load_feature_rows()
    if len(train) < 200:
        raise SystemExit("Need synthetic features — run generate_synthetic_india first")

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
            bags = train_logistic_bagged(Xtr_s, ytr_i, bags=9, epochs=300)
            ptr = [predict_bag_log(bags, x) for x in Xtr_s]
            pva = [predict_bag_log(bags, x) for x in Xva_s]
            temp = fit_temperature(pva, yva_i, is_prob=True)
            # apply temp for reported metrics
            def apply_t(p):
                p = min(max(p, 1e-6), 1 - 1e-6)
                z = math.log(p / (1 - p)) / temp
                return sigmoid(z)

            pva_c = [apply_t(p) for p in pva]
            ptr_c = [apply_t(p) for p in ptr]
            metrics = {
                "train_acc": round(acc(ytr_i, ptr_c), 4),
                "val_acc": round(acc(yva_i, pva_c), 4),
                "temperature": temp,
            }
            # flatten bags to avg weights for portable loader
            n_f = len(bags[0]["w"])
            w_avg = [sum(b["w"][j] for b in bags) / len(bags) for j in range(n_f)]
            b_avg = sum(b["b"] for b in bags) / len(bags)
            models_out[name] = {
                "type": "logistic",
                "weights": w_avg,
                "bias": b_avg,
                "temperature": temp,
                "ensemble_bags": len(bags),
                "metrics": metrics,
            }
        else:
            ytr_n = [v / 100 for v in ytr]
            bags = train_ridge_bagged(Xtr_s, ytr_n, bags=9, epochs=400)
            ptr = [predict_bag_ridge(bags, x) * 100 for x in Xtr_s]
            pva = [predict_bag_ridge(bags, x) * 100 for x in Xva_s]
            metrics = {
                "train_mae": round(mae(ytr, ptr), 3),
                "val_mae": round(mae(yva, pva), 3),
            }
            n_f = len(bags[0]["w"])
            w_avg = [sum(b["w"][j] for b in bags) / len(bags) for j in range(n_f)]
            b_avg = sum(b["b"] for b in bags) / len(bags)
            models_out[name] = {
                "type": "ridge",
                "weights": w_avg,
                "bias": b_avg,
                "ensemble_bags": len(bags),
                "metrics": metrics,
            }
        log(f"  {name}: {models_out[name]['metrics']}")

    bundle = {
        "version": "india_l2_v3",
        "trained_on": "synthetic_india_v3_features",
        "feature_columns": cols,
        "standardize": {"means": means, "stds": stds},
        "models": models_out,
        "cost": "zero",
        "notes": "Bagged ensembles + v3 interactions + temperature calibration.",
    }
    MODELS.mkdir(parents=True, exist_ok=True)
    for name in ("india_l2_bundle_v3.json", "india_l2_bundle_v2.json", "india_l2_bundle.json"):
        (MODELS / name).write_text(json.dumps(bundle, indent=2))
    log("Saved india_l2_bundle_v3 (+ aliases)")
    return bundle


def train_embedding_v3():
    log("=== L3 embedding v3 ===")
    VOCAB_SIZE, DIM = 768, 48

    def bow(name: str, category: str = "") -> list[float]:
        v = [0.0] * VOCAB_SIZE
        tokens = re.split(r"[^a-z0-9]+", (name + " " + category).lower())
        for t in tokens:
            if len(t) > 1:
                v[abs(hash(t)) % VOCAB_SIZE] += 1.0
            # bigrams
        for a, b in zip(tokens, tokens[1:]):
            if len(a) > 1 and len(b) > 1:
                bg = a + "_" + b
                v[abs(hash(bg)) % VOCAB_SIZE] += 0.5
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
            if i > 2500:
                break
            try:
                doc = json.loads(line)
                for lot in doc.get("lots") or []:
                    names.append((lot.get("name") or "", lot.get("asset_class") or ""))
            except Exception:
                continue
    # hard-coded India AMC diversity seeds
    seeds = [
        ("Parag Parikh Flexi Cap Fund Direct Growth", "mf"),
        ("Axis Bluechip Fund Regular Growth", "mf"),
        ("HDFC Flexi Cap Fund Direct Growth", "mf"),
        ("UTI Nifty 50 Index Fund Direct Growth", "mf"),
        ("SBI Small Cap Fund Regular Growth", "mf"),
        ("Mirae Asset Large Cap Fund Regular", "mf"),
        ("ICICI Prudential Bluechip Fund Direct", "mf"),
        ("Nippon India Large Cap Fund Direct", "mf"),
        ("Kotak Emerging Equity Fund Direct", "mf"),
        ("Quant Small Cap Fund Direct Growth", "mf"),
        ("HDFC Bank Ltd", "stock"),
        ("Reliance Industries Ltd", "stock"),
        ("SBI Fixed Deposit 3 Year", "fd"),
    ]
    names.extend(seeds)
    seen = set()
    uniq = []
    for n, c in names:
        k = n.lower().strip()
        if k and k not in seen:
            seen.add(k)
            uniq.append((n, c))
    names = uniq[:2200]
    log(f"  vocab names: {len(names)}")

    W = [[RNG.uniform(-0.04, 0.04) for _ in range(VOCAB_SIZE)] for _ in range(DIM)]
    b = [0.0] * DIM
    lr = 0.08
    for ep in range(40):
        loss = 0.0
        steps = 0
        for _ in range(min(1200, len(names) * 2)):
            n1, c1 = names[RNG.randrange(len(names))]
            n_pos = n1
            for a, rep in [
                ("Direct", ""),
                ("Regular", ""),
                ("Fund", ""),
                ("Growth", ""),
                ("  ", " "),
            ]:
                n_pos = n_pos.replace(a, rep)
            n_neg, c_neg = names[RNG.randrange(len(names))]
            tries = 0
            while n_neg.lower() == n1.lower() and tries < 12:
                n_neg, c_neg = names[RNG.randrange(len(names))]
                tries += 1

            def emb(n, c):
                return l2norm(matvec(W, bow(n, c), b))

            e1, ep_, en = emb(n1, c1), emb(n_pos, c1), emb(n_neg, c_neg)
            pos, neg = cosine(e1, ep_), cosine(e1, en)
            x1 = bow(n1, c1)
            for d in range(DIM):
                delta = lr * ((ep_[d] - e1[d]) - 0.55 * en[d])
                b[d] += 0.04 * delta
                for j in range(VOCAB_SIZE):
                    if x1[j] != 0:
                        W[d][j] += delta * x1[j]
            loss += max(0, 0.25 - pos + neg)
            steps += 1
        if ep % 8 == 0:
            log(f"  epoch {ep} margin_loss~{loss/max(1,steps):.4f}")

    bundle = {
        "version": "fund_embedding_v3",
        "type": "projection_bow_bigram_hardneg",
        "dim": DIM,
        "vocab_size": VOCAB_SIZE,
        "W": W,
        "b": b,
        "layer": "L3_dl",
        "n_names_seen": len(names),
        "cost": "zero",
    }
    # compact JSON (5 d.p.) — faster load on cloud-synced disks
    bundle["W"] = [[round(float(x), 5) for x in row] for row in bundle["W"]]
    bundle["b"] = [round(float(x), 5) for x in bundle["b"]]
    compact = json.dumps(bundle, separators=(",", ":"))
    for name in (
        "fund_embedding_v3.json",
        "fund_embedding_v2.json",
        "fund_embedding_v1.json",
    ):
        (MODELS / name).write_text(compact)
    log(f"Saved fund_embedding_v3 (+ aliases) size={len(compact)}")
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
        mean * 252,
        std * math.sqrt(252),
        mdd,
        mom_20,
        mom_60,
        min(rets),
        max(rets),
        last[0],
        last[1],
        last[2],
        last[3],
        last[4],
        len(rets) / 252,
        1.0 if mean > 0 else 0.0,
        abs(mean) / (std + 1e-6),
        (navs[-1] / navs[0] - 1) if navs[0] else 0,
    ]


def train_sequence_v3():
    log("=== L3 sequence v3 ===")
    import json as _json
    import urllib.request

    def fetch_nav_series(code: str, limit: int = 180) -> list[float]:
        try:
            with urllib.request.urlopen(f"https://api.mfapi.in/mf/{code}", timeout=10) as r:
                data = _json.loads(r.read().decode())
            navs = [float(x["nav"]) for x in (data.get("data") or [])[:limit]]
            navs.reverse()
            return navs
        except Exception:
            return []

    samples = []
    amfi = ROOT / "data" / "india" / "amfi_seed_funds.json"
    if amfi.exists():
        for s in _json.loads(amfi.read_text())[:25]:
            code = str(s.get("schemeCode") or "")
            if not code:
                continue
            navs = fetch_nav_series(code, 180)
            if len(navs) > 20:
                samples.append(navs)
    for p in (ROOT / "data" / "india").glob("nav_history_sample_*.json"):
        hist = _json.loads(p.read_text())
        navs = [float(x["nav"]) for x in reversed((hist.get("data") or [])[:180])]
        if len(navs) > 20:
            samples.append(navs)
    for _ in range(120):
        p = 100.0
        path = [p]
        mu = RNG.gauss(0.00045, 0.00035)
        sig = RNG.uniform(0.005, 0.022)
        for _d in range(140):
            p *= math.exp(RNG.gauss(mu, sig))
            path.append(p)
        samples.append(path)
    log(f"  series: {len(samples)}")

    X = [sequence_features_local(s) for s in samples]
    y_ret, y_risk = [], []
    for s in samples:
        mid = len(s) // 2
        r = s[-1] / s[mid] - 1 if mid > 0 and s[mid] else 0
        y_ret.append(max(-0.5, min(0.5, r)))
        rets = [s[i] / s[i - 1] - 1 for i in range(1, len(s)) if s[i - 1] > 0]
        std = math.sqrt(sum(x * x for x in rets) / max(1, len(rets))) if rets else 0.1
        y_risk.append(min(0.7, std * math.sqrt(252)))

    in_dim = len(X[0])
    hidden = 40
    W1 = [[RNG.uniform(-0.07, 0.07) for _ in range(in_dim)] for _ in range(hidden)]
    b1 = [0.0] * hidden
    W2 = [[RNG.uniform(-0.07, 0.07) for _ in range(hidden)] for _ in range(2)]
    b2 = [0.0, 0.0]
    lr = 0.012
    for ep in range(160):
        total = 0.0
        order = list(range(len(X)))
        RNG.shuffle(order)
        for i in order:
            h = [
                max(0.0, b1[k] + sum(W1[k][j] * X[i][j] for j in range(in_dim)))
                for k in range(hidden)
            ]
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
        if ep % 40 == 0:
            log(f"  epoch {ep} mse~{total/max(1,len(X)):.5f}")

    bundle = {
        "version": "nav_sequence_v3",
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
    for name in ("nav_sequence_v3.json", "nav_sequence_v2.json", "nav_sequence_v1.json"):
        (MODELS / name).write_text(json.dumps(bundle))
    log("Saved nav_sequence_v3 (+ aliases)")
    return bundle


def eval_ocr():
    log("=== OCR engine eval v3 ===")
    REPORTS.mkdir(parents=True, exist_ok=True)
    from app.intelligence.ocr.synthetic_screens import random_holdings, render_portfolio_image
    from app.intelligence.ocr.engine import ocr_image_bytes, ocr_available
    from app.intelligence.ocr.layout import parse_holdings_from_ocr_text

    status = ocr_available()
    log(f"  ocr_available: {status}")
    results = []
    for i in range(12):
        holdings = random_holdings(n=RNG.randint(3, 5))
        png, plain = render_portfolio_image(holdings, title=f"Portfolio {i}")
        parsed_text = parse_holdings_from_ocr_text(plain)
        # full image OCR — limited passes for train speed
        img_result = ocr_image_bytes(png, max_passes=3)
        gt_names = {h["name"].lower()[:20] for h in holdings}
        text_names = {l["name"].lower()[:20] for l in parsed_text.get("lots") or []}
        ocr_names = {l["name"].lower()[:20] for l in img_result.get("lots") or []}

        def recall(pred, gt):
            if not gt:
                return 0.0
            hit = 0
            for g in gt:
                if any(g[:10] in p or p[:10] in g for p in pred):
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
        log(
            f"  img {i}: layout={results[-1]['layout_on_plaintext_recall']} "
            f"ocr={results[-1]['full_ocr_recall']}"
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
        "stack": "Pillow multi-preprocess → multi-PSM Tesseract → layout v3 → india_portfolio_v1",
        "engine": "nxance_ocr_v3",
    }
    (REPORTS / "ocr_eval_report.json").write_text(json.dumps(report, indent=2))
    (MODELS / "ocr_eval_report.json").write_text(json.dumps(report, indent=2))
    log(f"  layout recall={avg_layout:.3f} full_ocr_recall={avg_ocr:.3f}")
    return report


def main():
    MODELS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    import importlib.util

    gen_path = ROOT / "training" / "scripts" / "generate_synthetic_india.py"
    spec = importlib.util.spec_from_file_location("gen_syn", gen_path)
    gen_mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(gen_mod)
    log("Refreshing synthetic set (1500/350)…")
    gen_mod.main(1500, 350)

    l2 = train_l2_v3()
    emb = train_embedding_v3()
    seq = train_sequence_v3()
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
            "engine": ocr.get("engine"),
        },
        "cost": "₹0",
        "stack": "L1 quant · L2 bagged ML v3 · L3 embedding+sequence v3 · OCR v3",
    }
    (REPORTS / "worldclass_zero_cost_summary.json").write_text(json.dumps(summary, indent=2))
    log("=== SUMMARY ===")
    log(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
