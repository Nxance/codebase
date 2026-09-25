"""L1 — risk snapshots from portfolio structure (no price series yet)."""
from __future__ import annotations

from .metrics import hhi


def concentration_flags(weights: list[float], n_holdings: int) -> dict:
    h = hhi(weights) if weights else 0.0
    return {
        "hhi": h,
        "concentrated": h > 0.35 or n_holdings <= 2,
        "layer": "L1_quant",
    }


def portfolio_risk_snapshot(
    holdings: list[dict],
    total_value: float,
    risk_bucket: str,
) -> dict:
    if total_value <= 0:
        return {"equity_pct": 0, "mismatch": False, "layer": "L1_quant"}
    eq = sum(
        h["current_value"]
        for h in holdings
        if h.get("asset_class") in ("mutual_fund", "stock")
    )
    equity_pct = round(eq / total_value * 100, 1)
    mismatch = (risk_bucket == "conservative" and equity_pct > 70) or (
        risk_bucket == "aggressive" and equity_pct < 40
    )
    weights = [h["current_value"] / total_value for h in holdings]
    conc = concentration_flags(weights, len(holdings))
    return {
        "equity_pct": equity_pct,
        "risk_goal_mismatch": mismatch,
        "hhi": conc["hhi"],
        "concentrated": conc["concentrated"],
        "layer": "L1_quant",
        "notes": (
            "Portfolio risk profile may not match stated comfort."
            if mismatch
            else "Risk profile broadly consistent with answers."
        ),
    }
