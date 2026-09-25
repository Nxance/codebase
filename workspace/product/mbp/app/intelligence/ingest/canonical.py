"""Normalize india_portfolio_v1 lots → engine holding rows."""
from __future__ import annotations

from typing import Any


def validate_minimal(doc: dict) -> list[str]:
    errors = []
    if doc.get("schema_version") != "india_portfolio_v1":
        errors.append("schema_version must be india_portfolio_v1")
    if not doc.get("lots"):
        errors.append("lots empty")
    for i, lot in enumerate(doc.get("lots") or []):
        if not lot.get("name"):
            errors.append(f"lot[{i}] missing name")
        if float(lot.get("current_value") or 0) <= 0 and float(lot.get("invested_amount") or 0) <= 0:
            errors.append(f"lot[{i}] no value")
    return errors


def lots_to_engine_holdings(lots: list[dict]) -> list[dict]:
    """Map canonical lots to current HC engine holding shape."""
    out = []
    for lot in lots:
        ac = (lot.get("asset_class") or "mutual_fund_equity").lower()
        if "stock" in ac or ac == "equity_stock":
            engine_ac = "stock"
        elif ac == "fd" or "ppf" in ac:
            engine_ac = "fd"
        else:
            engine_ac = "mutual_fund"
        plan = lot.get("plan_type") or "regular"
        if plan not in ("direct", "regular"):
            plan = "regular" if engine_ac == "mutual_fund" else "regular"
        inv = float(lot.get("invested_amount") or 0)
        cur = float(lot.get("current_value") or inv)
        out.append(
            {
                "name": lot.get("name"),
                "scheme_code": lot.get("amfi_code"),
                "current_value": cur,
                "invested_amount": inv or cur,
                "units": lot.get("quantity"),
                "plan_type": plan if engine_ac == "mutual_fund" else "regular",
                "purchase_date": (lot.get("purchase_date") or "2021-01-01")[:10],
                "asset_class": engine_ac,
                # India extras retained for metrics
                "isin": lot.get("isin"),
                "sector": lot.get("sector"),
                "market_cap_bucket": lot.get("market_cap_bucket"),
                "coupon_or_rate": lot.get("coupon_or_rate"),
                "canonical_asset_class": lot.get("asset_class"),
            }
        )
    return out


def engine_holdings_to_lots(holdings: list[dict]) -> list[dict]:
    """Best-effort reverse map for India metrics on current API holdings."""
    lots = []
    for i, h in enumerate(holdings):
        ac = h.get("asset_class") or "mutual_fund"
        if ac == "stock":
            cac = "equity_stock"
        elif ac == "fd":
            cac = "fd"
        else:
            cac = "mutual_fund_equity"
        lots.append(
            {
                "lot_id": f"eng_{i}",
                "asset_class": cac,
                "name": h.get("name"),
                "amfi_code": h.get("scheme_code"),
                "plan_type": h.get("plan_type") or "regular",
                "quantity": h.get("units") or 1,
                "avg_cost": 0,
                "invested_amount": float(h.get("invested_amount") or 0),
                "current_value": float(h.get("current_value") or 0),
                "purchase_date": h.get("purchase_date"),
                "sector": h.get("sector") or "unknown",
                "market_cap_bucket": h.get("market_cap_bucket") or "multi",
                "coupon_or_rate": h.get("coupon_or_rate"),
            }
        )
    return lots
