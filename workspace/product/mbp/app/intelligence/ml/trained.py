"""
Load trained India L2 bundle and score portfolios.

Prefers v2/v3 bundles; falls back gracefully.
Supports flat averaged weights and full bag ensembles.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[3]
MODELS = ROOT / "training" / "models"
# Prefer newest available
CANDIDATES = [
    MODELS / "india_l2_bundle_v4.json",
    MODELS / "india_l2_bundle_v3.json",
    MODELS / "india_l2_bundle_v2.json",
    MODELS / "india_l2_bundle.json",
]


def resolve_bundle_path() -> Path:
    return next((p for p in CANDIDATES if p.exists()), CANDIDATES[-1])


# Back-compat alias (recomputed on each access via property-like helper)
BUNDLE_PATH = CANDIDATES[0]  # preferred; load_bundle resolves actual


def sigmoid(z: float) -> float:
    if z < -50:
        return 0.0
    if z > 50:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


@lru_cache(maxsize=1)
def load_bundle() -> Optional[dict]:
    for p in CANDIDATES:
        if p.exists():
            return json.loads(p.read_text())
    return None


def clear_bundle_cache() -> None:
    load_bundle.cache_clear()


def _standardize(x: list[float], means: list[float], stds: list[float]) -> list[float]:
    return [(x[j] - means[j]) / (stds[j] or 1.0) for j in range(len(means))]


def vectorize_features(feat: dict[str, float], columns: list[str]) -> list[float]:
    return [float(feat.get(c, 0.0)) for c in columns]


def _predict_model(model: dict, x: list[float]) -> float:
    """Return probability (logistic) or raw score (ridge, 0-1 space)."""
    from .boost import blend_linear_boost, model_has_boost, predict_stumps

    mtype = str(model.get("type") or "")
    is_log = "logistic" in mtype or model.get("type") in ("logistic", "logistic_ensemble")

    # Full bag ensemble
    bags = model.get("bags")
    if bags:
        preds = []
        for bag in bags:
            w = bag.get("w") or bag.get("weights") or []
            b = bag.get("b") if "b" in bag else bag.get("bias", 0.0)
            z = b + sum(w[j] * x[j] for j in range(min(len(w), len(x))))
            if is_log:
                preds.append(sigmoid(z))
            else:
                preds.append(z)
        linear = sum(preds) / len(preds)
    else:
        # Flat weights
        w = model.get("weights") or []
        b = model.get("bias", 0.0)
        z = b + sum(w[j] * x[j] for j in range(min(len(w), len(x))))
        if is_log:
            a = float(model.get("platt_a", 1.0))
            c = float(model.get("platt_b", 0.0))
            linear = sigmoid(a * z + c)
        else:
            linear = z

    # v4: optional pure-Python boosted stumps blended in
    if model_has_boost(model):
        task = "log" if is_log else "reg"
        boost_p = predict_stumps(model["boost_stumps"], x, task=task)
        bw = float(model.get("boost_weight", 0.45))
        return blend_linear_boost(linear, boost_p, boost_weight=bw, task=task)
    return linear


def predict_all(feat: dict[str, float]) -> dict[str, Any]:
    """Returns probabilities / scores from trained bundle."""
    from .feature_expand import expand_features

    bundle = load_bundle()
    if not bundle:
        return {
            "available": False,
            "backend": "untrained",
            "layer": "L2_ml",
        }
    cols = bundle["feature_columns"]
    expanded = expand_features(feat)
    # prefer expanded values, allow raw override
    merged = {**feat, **expanded}
    means = bundle["standardize"]["means"]
    stds = bundle["standardize"]["stds"]
    x = _standardize(vectorize_features(merged, cols), means, stds)
    out: dict[str, Any] = {
        "available": True,
        "backend": bundle.get("version", "unknown"),
        "layer": "L2_ml",
        "n_features": len(cols),
        "predictions": {},
    }
    for name, model in bundle["models"].items():
        raw = _predict_model(model, x)
        mtype = str(model.get("type") or "")
        is_ridge = "ridge" in mtype or name == "health_score"
        if is_ridge:
            score = max(0.0, min(100.0, float(raw) * 100.0))
            out["predictions"][name] = {
                "score": round(score, 1),
                "metrics": model.get("metrics"),
            }
        else:
            p = float(raw)
            temp = float(model.get("temperature", 1.0))
            if temp != 1.0 and 0.0 < p < 1.0:
                p = min(max(p, 1e-6), 1 - 1e-6)
                logit = math.log(p / (1 - p)) / temp
                p = sigmoid(logit)
            out["predictions"][name] = {
                "probability": round(p, 4),
                "flag": p >= float(model.get("threshold", 0.5)),
                "metrics": model.get("metrics"),
            }
    return out


def build_feature_dict_from_engine(
    *,
    portfolio_xirr: float | None,
    ter_waste: float,
    overlap_waste: float,
    total_value: float,
    hhi_v: float,
    equity_pct: float,
    regular_aum_pct: float,
    top_sector_pct: float,
    smallcap_pct: float,
    liquid_pct: float,
    tax_drag: float,
    n_lots: int,
    sip_regularity: float,
    elss_locked_pct: float,
    fd_pct: float,
    mean_holding_years: float,
) -> dict[str, float]:
    tv = total_value or 1.0
    return {
        "portfolio_xirr": float(portfolio_xirr or 0),
        "ter_waste_pct_aum": 100 * ter_waste / tv,
        "overlap_waste_pct_aum": 100 * overlap_waste / tv,
        "hhi": hhi_v,
        "equity_pct": equity_pct,
        "regular_aum_pct": regular_aum_pct,
        "top_sector_pct": top_sector_pct,
        "smallcap_pct": smallcap_pct,
        "liquid_pct": liquid_pct,
        "est_tax_drag_pct_aum": 100 * tax_drag / tv,
        "n_lots": float(n_lots),
        "sip_regularity": sip_regularity,
        "elss_locked_pct": elss_locked_pct,
        "fd_pct": fd_pct,
        "mean_holding_years": mean_holding_years,
    }
