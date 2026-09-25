"""
Pure-Python gradient-boosted decision stumps (₹0 — no sklearn / XGBoost).

Used for L2 classification & regression when trained bundle includes boost trees.
Inference is fast; training lives in training/scripts/train_worldclass_v4.py.
"""
from __future__ import annotations

from typing import Any


def predict_stumps(stumps: list[dict], x: list[float], *, task: str = "log") -> float:
    """
    stumps: list of {feature, threshold, left, right, lr}
    For logistic: returns probability via sigmoid of sum.
    For ridge/reg: returns raw score (0-1 scale expected for health).
    """
    import math

    s = 0.0
    for t in stumps:
        j = int(t["feature"])
        thr = float(t["threshold"])
        lr = float(t.get("lr", 1.0))
        val = x[j] if j < len(x) else 0.0
        s += lr * (float(t["left"]) if val <= thr else float(t["right"]))
    if task == "log":
        if s < -50:
            return 0.0
        if s > 50:
            return 1.0
        return 1.0 / (1.0 + math.exp(-s))
    return s


def blend_linear_boost(
    linear_pred: float,
    boost_pred: float,
    *,
    boost_weight: float = 0.45,
    task: str = "log",
) -> float:
    """Convex blend of bagged linear + boost for calibration stability."""
    w = max(0.0, min(1.0, boost_weight))
    out = (1.0 - w) * linear_pred + w * boost_pred
    if task == "log":
        return max(0.0, min(1.0, out))
    return out


def model_has_boost(model: dict[str, Any]) -> bool:
    return bool(model.get("boost_stumps"))
