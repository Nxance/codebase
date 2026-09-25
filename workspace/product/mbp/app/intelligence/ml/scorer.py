"""
L2 — Fund / instrument quality scorer.

MBP: interpretable weighted linear model on features.
Future: same `.predict(features)` interface backed by LightGBM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .features import extract_holding_features


@dataclass
class FundQualityScorer:
    """
    Transparent baseline. Weights chosen from domain priors, not fitted yet.
    When training data exists: fit booster, set backend='boosting', keep API.
    """

    backend: str = "weighted_linear"
    # Higher = better quality
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "ter": -12.0,  # high TER hurts
            "xirr": 1.5,
            "plan_regular": -8.0,
            "underperform_vs_port": -10.0,
            "is_fd": 2.0,  # stability bonus when appropriate
        }
    )
    bias: float = 70.0

    def predict(self, features: dict[str, float]) -> dict[str, Any]:
        raw = self.bias
        drivers = []
        for k, w in self.weights.items():
            v = float(features.get(k, 0))
            contrib = w * v
            raw += contrib
            if abs(contrib) >= 1.5:
                drivers.append({"feature": k, "value": v, "contribution": round(contrib, 2)})
        score = max(0.0, min(100.0, raw))
        # Confidence: low until real model trained
        confidence = 0.45 if self.backend == "weighted_linear" else 0.75
        drivers.sort(key=lambda d: abs(d["contribution"]), reverse=True)
        return {
            "score": round(score, 1),
            "confidence": confidence,
            "backend": self.backend,
            "drivers": drivers[:5],
            "layer": "L2_ml",
            "model_status": "prior_weights_not_fitted",
        }

    def predict_batch(self, feature_list: list[dict[str, float]]) -> list[dict[str, Any]]:
        return [self.predict(f) for f in feature_list]


_default = FundQualityScorer()


def score_holdings(
    holdings: list[dict], portfolio_xirr: float | None = None
) -> list[dict]:
    out = []
    for h in holdings:
        feats = extract_holding_features(h, portfolio_xirr)
        pred = _default.predict(feats)
        out.append(
            {
                "name": h.get("name"),
                "quality_score": pred["score"],
                "ml_confidence": pred["confidence"],
                "drivers": pred["drivers"],
                "layer": "L2_ml",
            }
        )
    return out


def score_universe(instruments: list[dict]) -> list[dict]:
    """Score construction candidates (name, ter_direct, expected_return, risk)."""
    scored = []
    for inst in instruments:
        feats = {
            "ter": float(inst.get("ter_direct") or inst.get("ter") or 0.5),
            "xirr": float(inst.get("expected_return_pct") or 10),
            "plan_regular": 0.0,
            "underperform_vs_port": 0.0,
            "is_fd": 1.0 if inst.get("type") == "fd" else 0.0,
            "is_mf": 1.0 if inst.get("type") == "mutual_fund" else 0.0,
            "is_stock": 1.0 if inst.get("type") == "stock" else 0.0,
            "return_pct": float(inst.get("expected_return_pct") or 10),
            "weight": 0.0,
            "log_value": 0.0,
        }
        pred = _default.predict(feats)
        row = {**inst, "fit_score": pred["score"], "ml": pred}
        scored.append(row)
    scored.sort(key=lambda x: x["fit_score"], reverse=True)
    return scored
