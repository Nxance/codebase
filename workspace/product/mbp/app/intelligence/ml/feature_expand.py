"""Shared feature expansion for train + inference (must match)."""
from __future__ import annotations

import math


BASE_FEATS = [
    "portfolio_xirr",
    "ter_waste_pct_aum",
    "overlap_waste_pct_aum",
    "hhi",
    "equity_pct",
    "regular_aum_pct",
    "top_sector_pct",
    "smallcap_pct",
    "liquid_pct",
    "est_tax_drag_pct_aum",
    "n_lots",
    "sip_regularity",
    "elss_locked_pct",
    "fd_pct",
    "mean_holding_years",
]


def expand_features(row: dict) -> dict:
    """
    Interaction + India portfolio structure features.
    Free accuracy boost — no external data needed.
    """
    f = {k: float(row.get(k) or 0) for k in BASE_FEATS}
    # Core interactions (v2)
    f["ter_x_regular"] = f["ter_waste_pct_aum"] * (f["regular_aum_pct"] / 100)
    f["overlap_x_hhi"] = f["overlap_waste_pct_aum"] * f["hhi"]
    f["risk_proxy"] = f["smallcap_pct"] * 0.4 + (100 - f["liquid_pct"]) * 0.3 + f["hhi"] * 50
    f["cost_drag"] = (
        f["ter_waste_pct_aum"] + f["overlap_waste_pct_aum"] + f["est_tax_drag_pct_aum"] * 0.2
    )
    f["quality_proxy"] = f["portfolio_xirr"] - f["cost_drag"] * 2 - f["hhi"] * 10
    f["log_n_lots"] = math.log1p(f["n_lots"])
    f["equity_x_small"] = f["equity_pct"] * f["smallcap_pct"] / 100
    # v3 extras (only used when model bundle feature_columns include them)
    f["diversification"] = max(0.0, 1.0 - f["hhi"]) * math.log1p(f["n_lots"])
    f["illiquid_risk"] = (100 - f["liquid_pct"]) * (1.0 + f["elss_locked_pct"] / 100)
    f["plan_cost_stress"] = f["regular_aum_pct"] * f["ter_waste_pct_aum"] / 100
    f["concentration_equity"] = f["hhi"] * (f["equity_pct"] / 100)
    f["horizon_x_equity"] = f["mean_holding_years"] * (f["equity_pct"] / 100)
    f["cash_drag"] = f["fd_pct"] * 0.4 + max(0.0, f["liquid_pct"] - 15) * 0.3
    f["sip_discipline"] = f["sip_regularity"] * math.log1p(f["n_lots"])
    f["tax_x_horizon"] = f["est_tax_drag_pct_aum"] * f["mean_holding_years"]
    # v4 extras — India retail portfolio structure (free)
    f["cost_intensity"] = f["cost_drag"] / max(1.0, f["portfolio_xirr"] + 5.0)
    f["fragility"] = f["hhi"] * (1.0 + f["illiquid_risk"] / 100.0)
    f["balance_score"] = (
        (1.0 - abs(f["equity_pct"] - 60) / 100.0)
        * max(0.0, 1.0 - f["hhi"])
        * (1.0 - min(f["fd_pct"], 40) / 100.0)
    )
    f["leak_composite"] = (
        0.4 * f["ter_waste_pct_aum"]
        + 0.35 * f["overlap_waste_pct_aum"]
        + 0.25 * f["est_tax_drag_pct_aum"]
    )
    f["equity_concentration"] = (f["equity_pct"] / 100.0) * f["hhi"] * math.log1p(f["n_lots"])
    f["liquidity_buffer"] = f["liquid_pct"] + f["fd_pct"] * 0.5
    f["return_after_drag"] = f["portfolio_xirr"] - f["leak_composite"]
    f["plan_quality"] = max(0.0, 100.0 - f["regular_aum_pct"]) * (1.0 - f["ter_waste_pct_aum"] / 50.0)
    return f
