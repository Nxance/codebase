#!/usr/bin/env python3
"""
World-class-at-₹0 training pipeline v4.

Upgrades over v3:
  - L2: bagged logistic/ridge + pure-Python gradient-boosted stumps + v4 features
  - L3: embedding compact + style-factor aware eval
  - OCR: layout v4 + lexicon corrector eval (garbled name recovery)

Outputs:
  india_l2_bundle_v4.json (aliases → v3/v2/v1 paths for runtime preference)
  fund_embedding_v3.json (refreshed compact)
  nav_sequence_v3.json
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
RNG = random.Random(20260714)


def log(msg: str):
    print(msg, flush=True)


from app.intelligence.ml.feature_expand import expand_features  # noqa: E402


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


def train_logistic_bagged(X, y, bags=9, epochs=280, lr=0.05):
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


def train_ridge_bagged(X, y, bags=9, epochs=380, lr=0.012):
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


def train_boosted_stumps(X, y, *, task="log", n_trees=48, lr=0.12, max_thresholds=12):
    """
    Pure-Python gradient boosting with depth-1 trees (stumps).
    task=log: y in {0,1}; task=reg: y continuous.
    """
    n = len(X)
    n_f = len(X[0])
    # feature quantiles for candidate thresholds
    thresholds = []
    for j in range(n_f):
        col = sorted(X[i][j] for i in range(n))
        qs = []
        for t in range(1, max_thresholds):
            qs.append(col[min(n - 1, int(n * t / max_thresholds))])
        thresholds.append(sorted(set(qs)))

    if task == "log":
        # init with log-odds of base rate
        p0 = sum(y) / max(1, n)
        p0 = min(max(p0, 0.01), 0.99)
        F = [math.log(p0 / (1 - p0))] * n
    else:
        F = [0.0] * n

    stumps = []
    for _t in range(n_trees):
        if task == "log":
            # negative gradient of log-loss = y - p
            resid = []
            for i in range(n):
                p = sigmoid(F[i])
                resid.append(y[i] - p)
        else:
            resid = [y[i] - F[i] for i in range(n)]

        best = None
        best_loss = 1e18
        # subsample features for speed (free "random forest" vibe)
        feat_idx = list(range(n_f))
        RNG.shuffle(feat_idx)
        feat_idx = feat_idx[: max(8, n_f // 2)]

        for j in feat_idx:
            for thr in thresholds[j]:
                left_s = left_c = right_s = right_c = 0.0
                for i in range(n):
                    if X[i][j] <= thr:
                        left_s += resid[i]
                        left_c += 1
                    else:
                        right_s += resid[i]
                        right_c += 1
                if left_c < 8 or right_c < 8:
                    continue
                lv = left_s / left_c
                rv = right_s / right_c
                # SSE of residuals after fit
                loss = 0.0
                for i in range(n):
                    pred = lv if X[i][j] <= thr else rv
                    d = resid[i] - pred
                    loss += d * d
                if loss < best_loss:
                    best_loss = loss
                    best = {"feature": j, "threshold": thr, "left": lv, "right": rv, "lr": lr}

        if best is None:
            break
        stumps.append(best)
        for i in range(n):
            delta = best["left"] if X[i][best["feature"]] <= best["threshold"] else best["right"]
            F[i] += lr * delta

    # round for compact JSON
    compact = []
    for s in stumps:
        compact.append(
            {
                "feature": int(s["feature"]),
                "threshold": round(float(s["threshold"]), 5),
                "left": round(float(s["left"]), 5),
                "right": round(float(s["right"]), 5),
                "lr": round(float(s["lr"]), 5),
            }
        )
    return compact


def predict_boost(stumps, x, task="log"):
    s = 0.0
    for t in stumps:
        j = t["feature"]
        s += t["lr"] * (t["left"] if x[j] <= t["threshold"] else t["right"])
    if task == "log":
        return sigmoid(s)
    return s


def acc(y, p, thr=0.5):
    return sum(1 for yt, yp in zip(y, p) if int(yp >= thr) == yt) / max(1, len(y))


def mae(y, p):
    return sum(abs(a - b) for a, b in zip(y, p)) / max(1, len(y))


def fit_temperature(logits_or_p, y, is_prob=True):
    if is_prob:
        ps = [min(max(p, 1e-6), 1 - 1e-6) for p in logits_or_p]
        logits = [math.log(p / (1 - p)) for p in ps]
    else:
        logits = logits_or_p
    best_t, best_nll = 1.0, 1e18
    for t in [0.55, 0.7, 0.85, 1.0, 1.2, 1.5, 2.0, 2.5]:
        nll = 0.0
        for z, yt in zip(logits, y):
            p = sigmoid(z / t)
            p = min(max(p, 1e-6), 1 - 1e-6)
            nll -= yt * math.log(p) + (1 - yt) * math.log(1 - p)
        nll /= max(1, len(y))
        if nll < best_nll:
            best_nll, best_t = nll, t
    return best_t


def train_l2_v4():
    log("=== L2 ensemble v4 (bags + boost + v4 features) ===")
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
            bags = train_logistic_bagged(Xtr_s, ytr_i, bags=9, epochs=280)
            stumps = train_boosted_stumps(Xtr_s, ytr_i, task="log", n_trees=40, lr=0.14)
            bw = 0.42

            def pred_one(x):
                pl = predict_bag_log(bags, x)
                pb = predict_boost(stumps, x, task="log")
                return (1 - bw) * pl + bw * pb

            ptr = [pred_one(x) for x in Xtr_s]
            pva = [pred_one(x) for x in Xva_s]
            temp = fit_temperature(pva, yva_i, is_prob=True)

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
                "n_boost_stumps": len(stumps),
            }
            n_f = len(bags[0]["w"])
            w_avg = [sum(b["w"][j] for b in bags) / len(bags) for j in range(n_f)]
            b_avg = sum(b["b"] for b in bags) / len(bags)
            models_out[name] = {
                "type": "logistic",
                "weights": w_avg,
                "bias": b_avg,
                "temperature": temp,
                "ensemble_bags": len(bags),
                "boost_stumps": stumps,
                "boost_weight": bw,
                "metrics": metrics,
            }
        else:
            ytr_n = [v / 100 for v in ytr]
            bags = train_ridge_bagged(Xtr_s, ytr_n, bags=9, epochs=360)
            stumps = train_boosted_stumps(Xtr_s, ytr_n, task="reg", n_trees=36, lr=0.1)
            bw = 0.4

            def pred_r(x):
                pl = predict_bag_ridge(bags, x)
                pb = predict_boost(stumps, x, task="reg")
                return (1 - bw) * pl + bw * pb

            ptr = [pred_r(x) * 100 for x in Xtr_s]
            pva = [pred_r(x) * 100 for x in Xva_s]
            metrics = {
                "train_mae": round(mae(ytr, ptr), 3),
                "val_mae": round(mae(yva, pva), 3),
                "n_boost_stumps": len(stumps),
            }
            n_f = len(bags[0]["w"])
            w_avg = [sum(b["w"][j] for b in bags) / len(bags) for j in range(n_f)]
            b_avg = sum(b["b"] for b in bags) / len(bags)
            models_out[name] = {
                "type": "ridge",
                "weights": w_avg,
                "bias": b_avg,
                "ensemble_bags": len(bags),
                "boost_stumps": stumps,
                "boost_weight": bw,
                "metrics": metrics,
            }
        log(f"  {name}: {models_out[name]['metrics']}")

    bundle = {
        "version": "india_l2_v4",
        "trained_on": "synthetic_india_v4_features",
        "feature_columns": cols,
        "standardize": {"means": means, "stds": stds},
        "models": models_out,
        "cost": "zero",
        "notes": "Bagged linear + pure-Python GBM stumps + v4 interactions + temperature.",
    }
    MODELS.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(bundle, indent=2)
    for name in (
        "india_l2_bundle_v4.json",
        "india_l2_bundle_v3.json",
        "india_l2_bundle_v2.json",
        "india_l2_bundle.json",
    ):
        (MODELS / name).write_text(payload)
    log("Saved india_l2_bundle_v4 (+ aliases)")
    return bundle


def train_embedding_refresh():
    """Compact refresh of v3 embedding (same architecture, cleaner file)."""
    log("=== L3 embedding refresh (compact) ===")
    # Reuse v3 trainer logic inline (avoid full 40-epoch if file exists & ok)
    emb_path = MODELS / "fund_embedding_v3.json"
    if emb_path.exists():
        try:
            m = json.loads(emb_path.read_text())
            if m.get("W") and m.get("dim"):
                # re-compact
                m["W"] = [[round(float(x), 5) for x in row] for row in m["W"]]
                m["b"] = [round(float(x), 5) for x in m["b"]]
                m["style_factors"] = True
                m["version"] = m.get("version") or "fund_embedding_v3"
                compact = json.dumps(m, separators=(",", ":"))
                for name in (
                    "fund_embedding_v3.json",
                    "fund_embedding_v2.json",
                    "fund_embedding_v1.json",
                ):
                    (MODELS / name).write_text(compact)
                log(f"  refreshed compact embedding size={len(compact)}")
                return m
        except Exception as e:
            log(f"  refresh failed ({e}); skip retrain in v4 (use existing)")
    return {"version": "fund_embedding_v3", "note": "unchanged"}


def eval_style_overlap():
    from app.intelligence.dl.models import portfolio_embedding_overlap

    holdings = [
        {"name": "Axis Bluechip Fund Direct", "asset_class": "mutual_fund"},
        {"name": "ICICI Prudential Bluechip Fund Direct", "asset_class": "mutual_fund"},
        {"name": "SBI Small Cap Fund Regular", "asset_class": "mutual_fund"},
        {"name": "HDFC Bank Ltd", "asset_class": "stock"},
    ]
    r = portfolio_embedding_overlap(holdings)
    log(
        f"  style overlap: n_pairs={r['n_pairs']} max={r['max_similarity']} "
        f"cluster={r['cluster_risk']} hist={r.get('style_histogram')}"
    )
    return r


def eval_ocr_v4():
    log("=== OCR engine eval v4 ===")
    REPORTS.mkdir(parents=True, exist_ok=True)
    from app.intelligence.ocr.synthetic_screens import random_holdings, render_portfolio_image
    from app.intelligence.ocr.engine import ocr_image_bytes, ocr_available
    from app.intelligence.ocr.layout import parse_holdings_from_ocr_text
    from app.intelligence.ocr.lexicon import correct_name

    status = ocr_available()
    log(f"  ocr_available: {status}")

    # Lexicon recovery on intentionally garbled names
    garble_tests = [
        ("Parag Parlkh Flexi Cap", "parag parikh"),
        ("Axs Bluechip Fund", "axis bluechip"),
        ("UTI Nifty 5O Index", "uti nifty"),
        ("HDFC Flexl Cap Direct", "hdfc flexi"),
        ("SBl Small Cap Fund", "sbi small"),
    ]
    lex_hits = 0
    for raw, expect in garble_tests:
        fixed = correct_name(raw, min_score=0.35)
        ok = expect in fixed["name"].lower()
        if ok:
            lex_hits += 1
        log(f"  lex '{raw}' → '{fixed['name']}' score={fixed['score']} ok={ok}")
    lex_acc = lex_hits / len(garble_tests)

    results = []
    for i in range(10):
        holdings = random_holdings(n=RNG.randint(3, 5))
        png, plain = render_portfolio_image(holdings, title=f"Portfolio {i}")
        parsed_text = parse_holdings_from_ocr_text(plain)
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
                "lexicon_corrections": (parsed_text.get("source") or {}).get(
                    "lexicon_corrections", 0
                ),
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
        "lexicon_garble_acc": round(lex_acc, 3),
        "details": results,
        "cost": "zero",
        "stack": "Pillow → multi-PSM Tesseract → layout v4 → lexicon → india_portfolio_v1",
        "engine": "nxance_ocr_v4",
    }
    (REPORTS / "ocr_eval_report.json").write_text(json.dumps(report, indent=2))
    (MODELS / "ocr_eval_report.json").write_text(json.dumps(report, indent=2))
    log(
        f"  layout={avg_layout:.3f} ocr={avg_ocr:.3f} lexicon_garble={lex_acc:.3f}"
    )
    return report


def main():
    MODELS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    # Synthetic refresh only if thin
    train_csv = SYN / "features_train.csv"
    if not train_csv.exists() or sum(1 for _ in train_csv.open()) < 500:
        import importlib.util

        gen_path = ROOT / "training" / "scripts" / "generate_synthetic_india.py"
        spec = importlib.util.spec_from_file_location("gen_syn", gen_path)
        gen_mod = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(gen_mod)
        log("Refreshing synthetic set…")
        gen_mod.main(1500, 350)
    else:
        log("Using existing synthetic features")

    l2 = train_l2_v4()
    emb = train_embedding_refresh()
    style = eval_style_overlap()
    ocr = eval_ocr_v4()

    # Sequence: keep existing if present (nav fetch can be slow/offline)
    seq_path = MODELS / "nav_sequence_v3.json"
    seq_ver = "nav_sequence_v3" if seq_path.exists() else None
    if not seq_path.exists():
        log("nav_sequence missing — run train_worldclass_v3 for sequence MLP")

    summary = {
        "l2_version": l2.get("version"),
        "l2_metrics": {k: v.get("metrics") for k, v in l2.get("models", {}).items()},
        "embedding": emb.get("version"),
        "sequence": seq_ver,
        "style_overlap_sample": {
            "n_pairs": style.get("n_pairs"),
            "max_similarity": style.get("max_similarity"),
            "cluster_risk": style.get("cluster_risk"),
            "style_histogram": style.get("style_histogram"),
        },
        "ocr": {
            "ready": (ocr.get("ocr_status") or {}).get("ready"),
            "layout_recall": ocr.get("avg_layout_plaintext_recall"),
            "ocr_recall": ocr.get("avg_full_ocr_recall"),
            "lexicon_garble_acc": ocr.get("lexicon_garble_acc"),
            "engine": ocr.get("engine"),
        },
        "cost": "₹0",
        "stack": (
            "L1 quant · L2 bags+boost ML v4 · L3 embedding+style+sequence · OCR v4 lexicon"
        ),
    }
    (REPORTS / "worldclass_zero_cost_summary.json").write_text(json.dumps(summary, indent=2))
    log("=== SUMMARY ===")
    log(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
