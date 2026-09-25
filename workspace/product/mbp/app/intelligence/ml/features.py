"""L2 — feature extraction for tabular ML (rules today, LightGBM tomorrow)."""
from __future__ import annotations

from typing import Any


def extract_holding_features(h: dict, portfolio_xirr: float | None = None) -> dict[str, float]:
    """
    Numeric feature vector. Stable keys so a trained model can drop in later.
    """
    ter = float(h.get("ter") or 0)
    xirr = h.get("xirr")
    ret = float(h.get("return_pct") or 0)
    plan_regular = 1.0 if h.get("plan_type") == "regular" else 0.0
    is_mf = 1.0 if h.get("asset_class") == "mutual_fund" else 0.0
    is_fd = 1.0 if h.get("asset_class") == "fd" else 0.0
    is_stock = 1.0 if h.get("asset_class") == "stock" else 0.0
    weight = float(h.get("weight") or 0)
    underperform = 0.0
    if xirr is not None and portfolio_xirr is not None:
        underperform = 1.0 if xirr < portfolio_xirr - 2 else 0.0
    return {
        "ter": ter,
        "xirr": float(xirr) if xirr is not None else ret,
        "return_pct": ret,
        "plan_regular": plan_regular,
        "is_mf": is_mf,
        "is_fd": is_fd,
        "is_stock": is_stock,
        "weight": weight,
        "underperform_vs_port": underperform,
        "log_value": __import__("math").log1p(float(h.get("current_value") or 0)),
    }


def extract_portfolio_features(
    holdings: list[dict],
    *,
    portfolio_xirr: float | None,
    ter_waste: float,
    overlap_waste: float,
    hhi: float,
    equity_pct: float,
) -> dict[str, float]:
    n = len(holdings)
    regular_share = (
        sum(1 for h in holdings if h.get("plan_type") == "regular") / n if n else 0
    )
    return {
        "n_holdings": float(n),
        "portfolio_xirr": float(portfolio_xirr or 0),
        "ter_waste_rs": ter_waste,
        "overlap_waste_rs": overlap_waste,
        "hhi": hhi,
        "equity_pct": equity_pct,
        "regular_share": regular_share,
    }
