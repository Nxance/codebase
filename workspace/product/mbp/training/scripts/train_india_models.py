#!/usr/bin/env python3
"""
Train India-centric L2 models on synthetic features.

Uses pure Python logistic / ridge-style models so we stay zero-dependency
(no sklearn required on Python 3.14). Artefacts are JSON weights loadable
by FundQualityScorer / PortfolioHealthModel in production.
"""
from __future__ import annotations

import csv
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "synthetic"
MODELS = ROOT / "training" / "models"
REPORTS = ROOT / "training" / "reports"


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def to_float(row: dict, keys: list[str]) -> list[float]:
    return [float(row[k]) for k in keys]


def sigmoid(z: float) -> float:
    if z < -50:
        return 0.0
    if z > 50:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def train_logistic(
    X: list[list[float]],
    y: list[int],
    lr: float = 0.05,
    epochs: int = 400,
    l2: float = 0.01,
    seed: int = 0,
) -> dict:
    rng = random.Random(seed)
    n_f = len(X[0])
    w = [rng.uniform(-0.01, 0.01) for _ in range(n_f)]
    b = 0.0
    n = len(X)
    for ep in range(epochs):
        # shuffle
        idx = list(range(n))
        rng.shuffle(idx)
        for i in idx:
            z = b + sum(w[j] * X[i][j] for j in range(n_f))
            p = sigmoid(z)
            err = p - y[i]
            for j in range(n_f):
                w[j] -= lr * (err * X[i][j] + l2 * w[j])
            b -= lr * err
    return {"weights": w, "bias": b, "type": "logistic"}


def train_ridge(
    X: list[list[float]],
    y: list[float],
    lr: float = 0.01,
    epochs: int = 500,
    l2: float = 0.05,
    seed: int = 1,
) -> dict:
    """Simple SGD ridge for continuous health score."""
    rng = random.Random(seed)
    n_f = len(X[0])
    # normalize y to 0-1 for stability
    w = [rng.uniform(-0.01, 0.01) for _ in range(n_f)]
    b = 0.0
    n = len(X)
    for ep in range(epochs):
        idx = list(range(n))
        rng.shuffle(idx)
        for i in idx:
            pred = b + sum(w[j] * X[i][j] for j in range(n_f))
            err = pred - y[i]
            for j in range(n_f):
                w[j] -= lr * (err * X[i][j] + l2 * w[j])
            b -= lr * err
    return {"weights": w, "bias": b, "type": "ridge"}


def predict_logistic(model: dict, x: list[float]) -> float:
    z = model["bias"] + sum(model["weights"][j] * x[j] for j in range(len(x)))
    return sigmoid(z)


def predict_ridge(model: dict, x: list[float]) -> float:
    return model["bias"] + sum(model["weights"][j] * x[j] for j in range(len(x)))


def standardize(
    X: list[list[float]],
) -> tuple[list[list[float]], list[float], list[float]]:
    n_f = len(X[0])
    means = []
    stds = []
    for j in range(n_f):
        col = [row[j] for row in X]
        m = sum(col) / len(col)
        v = sum((c - m) ** 2 for c in col) / max(1, len(col) - 1)
        s = math.sqrt(v) or 1.0
        means.append(m)
        stds.append(s)
    Xs = [[(row[j] - means[j]) / stds[j] for j in range(n_f)] for row in X]
    return Xs, means, stds


def apply_standard(X: list[list[float]], means: list[float], stds: list[float]):
    return [[(row[j] - means[j]) / stds[j] for j in range(len(means))] for row in X]


def accuracy(y_true, y_prob, thr=0.5):
    correct = sum(1 for yt, yp in zip(y_true, y_prob) if int(yp >= thr) == yt)
    return correct / max(1, len(y_true))


def mae(y_true, y_pred):
    return sum(abs(a - b) for a, b in zip(y_true, y_pred)) / max(1, len(y_true))


def main():
    train_path = DATA / "features_train.csv"
    val_path = DATA / "features_val.csv"
    if not train_path.exists():
        print("Run generate_synthetic_india.py first")
        sys.exit(1)

    train = load_csv(train_path)
    val = load_csv(val_path)
    meta = json.loads((DATA / "labels_meta.json").read_text())
    feat_cols = meta["feature_columns"]

    Xtr = [to_float(r, feat_cols) for r in train]
    Xva = [to_float(r, feat_cols) for r in val]
    Xtr_s, means, stds = standardize(Xtr)
    Xva_s = apply_standard(Xva, means, stds)

    tasks = {
        "has_ter_leak": ("label_has_ter_leak", "logistic"),
        "has_overlap": ("label_has_overlap", "logistic"),
        "high_concentration": ("label_high_concentration", "logistic"),
        "tax_heavy": ("label_tax_heavy", "logistic"),
        "low_liquidity": ("label_low_liquidity", "logistic"),
        "health_score": ("label_health_score", "ridge"),
    }

    MODELS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    report = {"features": feat_cols, "means": means, "stds": stds, "models": {}}

    for name, (label_col, kind) in tasks.items():
        ytr = [float(r[label_col]) for r in train]
        yva = [float(r[label_col]) for r in val]
        if kind == "logistic":
            ytr_i = [int(v) for v in ytr]
            yva_i = [int(v) for v in yva]
            model = train_logistic(Xtr_s, ytr_i)
            ptr = [predict_logistic(model, x) for x in Xtr_s]
            pva = [predict_logistic(model, x) for x in Xva_s]
            metrics = {
                "train_acc": round(accuracy(ytr_i, ptr), 4),
                "val_acc": round(accuracy(yva_i, pva), 4),
                "val_pos_rate": round(sum(yva_i) / max(1, len(yva_i)), 4),
            }
        else:
            # scale score to 0-1
            ytr_n = [v / 100 for v in ytr]
            yva_n = [v / 100 for v in yva]
            model = train_ridge(Xtr_s, ytr_n)
            ptr = [predict_ridge(model, x) * 100 for x in Xtr_s]
            pva = [predict_ridge(model, x) * 100 for x in Xva_s]
            metrics = {
                "train_mae": round(mae(ytr, ptr), 3),
                "val_mae": round(mae(yva, pva), 3),
            }
        report["models"][name] = {
            "label": label_col,
            "kind": kind,
            "metrics": metrics,
            "weights": model["weights"],
            "bias": model["bias"],
        }
        print(name, metrics)

    # Export production bundle
    bundle = {
        "version": "india_l2_v1",
        "trained_on": "synthetic_india_multivariate",
        "feature_columns": feat_cols,
        "standardize": {"means": means, "stds": stds},
        "models": {
            k: {
                "type": v["kind"],
                "weights": v["weights"],
                "bias": v["bias"],
                "metrics": v["metrics"],
            }
            for k, v in report["models"].items()
        },
        "notes": (
            "Replace synthetic training with anonymised real CAS over time. "
            "Metrics are India-feature based (TER, overlap, sector, liquidity, tax drag)."
        ),
    }
    (MODELS / "india_l2_bundle.json").write_text(json.dumps(bundle, indent=2))
    (REPORTS / "train_report.json").write_text(json.dumps(report, indent=2))
    print("Saved", MODELS / "india_l2_bundle.json")


if __name__ == "__main__":
    main()
