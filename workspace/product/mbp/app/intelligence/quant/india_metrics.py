"""
India-centric quant metrics (L1).

Goes beyond XIRR/TER/overlap: tax buckets, ELSS lock-in, FD post-tax,
concentration by sector/cap, SIP discipline proxies, rupee cost drag.
All deterministic — training labels can be derived from these.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional


# India tax approximations for *labelling / education* (not legal advice)
# Equity LTCG >1y: 12.5% above 1.25L exemption simplified; STCG 20% (post-2024 regime simplified flags)
EQUITY_STCG_RATE = 0.20
EQUITY_LTCG_RATE = 0.125
DEBT_TAX_PROXY = 0.30  # slab proxy for training labels
FD_TDS_THRESHOLD = 40000  # illustrative


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def holding_period_days(purchase: Optional[str], as_of: Optional[date] = None) -> Optional[int]:
    d = _parse_date(purchase)
    if not d:
        return None
    as_of = as_of or date.today()
    return (as_of - d).days


def tax_bucket_india(asset_class: str, purchase: Optional[str], as_of: Optional[date] = None) -> str:
    """Coarse tax bucket for engines + training features."""
    ac = (asset_class or "").lower()
    days = holding_period_days(purchase, as_of)
    if "elss" in ac:
        return "elss_lockin" if days is not None and days < 365 * 3 else "equity_ltcg"
    if any(x in ac for x in ("equity", "stock", "index", "etf", "sgb")):
        if days is None:
            return "unknown"
        return "equity_stcg" if days < 365 else "equity_ltcg"
    if any(x in ac for x in ("debt", "fd", "ppf", "bond", "hybrid")):
        if "ppf" in ac:
            return "exempt"
        return "debt"
    return "unknown"


def estimated_tax_drag_rs(
    gain_rs: float,
    tax_bucket: str,
    *,
    ltcg_exemption_remaining: float = 125000,
) -> float:
    """Illustrative tax on *unrealised* gain if sold today — for ranking awareness."""
    if gain_rs <= 0:
        return 0.0
    if tax_bucket == "exempt":
        return 0.0
    if tax_bucket == "equity_stcg":
        return round(gain_rs * EQUITY_STCG_RATE, 2)
    if tax_bucket == "equity_ltcg":
        taxable = max(0.0, gain_rs - max(0.0, ltcg_exemption_remaining))
        return round(taxable * EQUITY_LTCG_RATE, 2)
    if tax_bucket in ("debt", "elss_lockin"):
        # ELSS still equity-like after lock; debt proxy slab
        if tax_bucket == "elss_lockin":
            return 0.0  # cannot sell
        return round(gain_rs * DEBT_TAX_PROXY, 2)
    return 0.0


def fd_post_tax_yield(rate_pct: float, slab: float = 0.30) -> float:
    """Post-tax FD yield approximation."""
    return round(rate_pct * (1 - slab), 3)


def elss_lockin_remaining_days(purchase: Optional[str], as_of: Optional[date] = None) -> Optional[int]:
    d = _parse_date(purchase)
    if not d:
        return None
    unlock = date(d.year + 3, d.month, min(d.day, 28))
    as_of = as_of or date.today()
    return max(0, (unlock - as_of).days)


def sector_concentration(lots: list[dict]) -> dict[str, Any]:
    total = sum(float(l.get("current_value") or 0) for l in lots) or 1.0
    sectors: dict[str, float] = {}
    for l in lots:
        sec = (l.get("sector") or "unknown").title()
        sectors[sec] = sectors.get(sec, 0) + float(l.get("current_value") or 0)
    weights = {k: round(v / total * 100, 2) for k, v in sectors.items()}
    top = max(weights.values()) if weights else 0
    return {
        "sector_weights_pct": weights,
        "top_sector_pct": top,
        "flag_high_sector": top >= 40,
        "layer": "L1_quant_india",
    }


def market_cap_mix(lots: list[dict]) -> dict[str, Any]:
    total = sum(float(l.get("current_value") or 0) for l in lots) or 1.0
    buckets = {"large": 0.0, "mid": 0.0, "small": 0.0, "multi": 0.0, "na": 0.0}
    for l in lots:
        b = (l.get("market_cap_bucket") or "na").lower()
        if b not in buckets:
            b = "na"
        buckets[b] += float(l.get("current_value") or 0)
    pct = {k: round(v / total * 100, 2) for k, v in buckets.items()}
    return {"cap_weights_pct": pct, "layer": "L1_quant_india"}


def direct_vs_regular_share(lots: list[dict]) -> dict[str, Any]:
    mf = [l for l in lots if "mutual_fund" in (l.get("asset_class") or "")]
    if not mf:
        return {"regular_aum_pct": 0, "direct_aum_pct": 0, "n_regular": 0, "n_direct": 0}
    tot = sum(float(l.get("current_value") or 0) for l in mf) or 1
    reg = sum(float(l.get("current_value") or 0) for l in mf if l.get("plan_type") == "regular")
    return {
        "regular_aum_pct": round(reg / tot * 100, 2),
        "direct_aum_pct": round(100 - reg / tot * 100, 2),
        "n_regular": sum(1 for l in mf if l.get("plan_type") == "regular"),
        "n_direct": sum(1 for l in mf if l.get("plan_type") == "direct"),
        "layer": "L1_quant_india",
    }


def liquidity_score(lots: list[dict]) -> dict[str, Any]:
    """0-100: higher = more liquid. ELSS lock, FD, PPF reduce score."""
    total = sum(float(l.get("current_value") or 0) for l in lots) or 1
    locked = 0.0
    for l in lots:
        ac = (l.get("asset_class") or "").lower()
        val = float(l.get("current_value") or 0)
        if "elss" in ac or "ppf" in ac or "epf" in ac or "nps" in ac:
            locked += val
        elif ac == "fd":
            locked += val * 0.5  # partial
        elif l.get("lock_in_until"):
            locked += val
    free_pct = 100 * (1 - locked / total)
    return {
        "liquid_pct": round(free_pct, 2),
        "locked_value_rs": round(locked, 2),
        "score_0_100": round(min(100, max(0, free_pct)), 1),
        "layer": "L1_quant_india",
    }


def sip_discipline_proxy(cashflows: list[dict], months: int = 12) -> dict[str, Any]:
    """From cashflow list: regularity of SIP-like negative flows."""
    sips = [c for c in cashflows if c.get("type") == "sip" and float(c.get("amount") or 0) < 0]
    if not sips:
        return {"sip_count": 0, "regularity_score": 0, "layer": "L1_quant_india"}
    # months with at least one SIP
    months_seen = set()
    for c in sips:
        d = _parse_date(c.get("date"))
        if d:
            months_seen.add((d.year, d.month))
    regularity = min(100, round(100 * len(months_seen) / max(months, 1), 1))
    return {
        "sip_count": len(sips),
        "active_months": len(months_seen),
        "regularity_score": regularity,
        "layer": "L1_quant_india",
    }


def compute_india_portfolio_metrics(
    lots: list[dict],
    cashflows: Optional[list[dict]] = None,
    *,
    as_of: Optional[date] = None,
) -> dict[str, Any]:
    """Aggregate India-centric metrics for a canonical portfolio."""
    as_of = as_of or date.today()
    enriched = []
    total_gain = 0.0
    tax_drag = 0.0
    for l in lots:
        inv = float(l.get("invested_amount") or 0)
        cur = float(l.get("current_value") or 0)
        gain = cur - inv
        total_gain += gain
        tb = tax_bucket_india(l.get("asset_class") or "", l.get("purchase_date"), as_of)
        drag = estimated_tax_drag_rs(gain, tb)
        tax_drag += drag
        row = {
            **l,
            "unrealised_gain_rs": round(gain, 2),
            "tax_bucket": tb,
            "est_tax_if_sold_rs": drag,
            "holding_days": holding_period_days(l.get("purchase_date"), as_of),
        }
        if "elss" in (l.get("asset_class") or ""):
            row["elss_lockin_days_left"] = elss_lockin_remaining_days(l.get("purchase_date"), as_of)
        if (l.get("asset_class") or "") == "fd" and l.get("coupon_or_rate"):
            row["fd_post_tax_yield_pct"] = fd_post_tax_yield(float(l["coupon_or_rate"]))
        enriched.append(row)

    return {
        "as_of": as_of.isoformat(),
        "n_lots": len(lots),
        "total_invested": round(sum(float(l.get("invested_amount") or 0) for l in lots), 2),
        "total_value": round(sum(float(l.get("current_value") or 0) for l in lots), 2),
        "unrealised_gain_rs": round(total_gain, 2),
        "est_tax_if_fully_sold_rs": round(tax_drag, 2),
        "sector": sector_concentration(lots),
        "market_cap": market_cap_mix(lots),
        "plan_mix": direct_vs_regular_share(lots),
        "liquidity": liquidity_score(lots),
        "sip": sip_discipline_proxy(cashflows or []),
        "lots_enriched": enriched,
        "metric_set": "india_v1",
        "layer": "L1_quant_india",
    }


# Feature names exported for ML training
INDIA_FEATURE_COLUMNS = [
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
