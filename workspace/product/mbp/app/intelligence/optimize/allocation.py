"""L4 — strategic asset allocation (policy + required return)."""
from __future__ import annotations


def strategic_allocation(
    *,
    years: float,
    risk_bucket: str,
    required_return_pct: float | None,
) -> dict:
    """
    Policy layer: maps horizon + risk → class weights.
    Not ML. Can become Black–Litterman later using L2 views.
    """
    if years < 3:
        base = {"equity": 20.0, "debt_mf": 30.0, "fd": 50.0}
    elif years < 7:
        base = {"equity": 50.0, "debt_mf": 30.0, "fd": 20.0}
    else:
        base = {"equity": 70.0, "debt_mf": 20.0, "fd": 10.0}

    if risk_bucket == "conservative":
        base["equity"] = max(10.0, base["equity"] - 20)
        base["fd"] += 15
        base["debt_mf"] += 5
    elif risk_bucket == "aggressive":
        base["equity"] = min(85.0, base["equity"] + 15)
        base["fd"] = max(5.0, base["fd"] - 10)
        base["debt_mf"] = max(10.0, base["debt_mf"] - 5)

    # If required return is high, tilt equity (capped)
    req = required_return_pct or 0
    if req > 14:
        base["equity"] = min(85.0, base["equity"] + 5)
        base["fd"] = max(5.0, base["fd"] - 5)
    if req > 30:
        # Infeasible signal — keep allocation but flag
        pass

    s = sum(base.values())
    allocation = {k: round(v / s * 100, 1) for k, v in base.items()}
    stock_share = 0.0
    if risk_bucket == "aggressive" and years >= 7:
        stock_share = 25.0
    elif risk_bucket == "balanced" and years >= 10:
        stock_share = 15.0

    blended = round(
        allocation["equity"] / 100 * min(max(req, 11), 15)
        + allocation["debt_mf"] / 100 * 7.2
        + allocation["fd"] / 100 * 6.9,
        2,
    )
    return {
        "allocation_pct": allocation,
        "stock_share_of_equity_pct": stock_share,
        "expected_blended_return_pct": blended,
        "method": "policy_rules_v1",
        "layer": "L4_optimize",
    }
