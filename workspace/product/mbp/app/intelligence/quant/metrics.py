"""L1 — deterministic metrics. No learning. No LLM."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional


def brent_root(f, a: float, b: float, maxiter: int = 1000, xtol: float = 1e-6) -> float:
    fa, fb = f(a), f(b)
    if fa * fb > 0:
        raise ValueError("Root not bracketed")
    for _ in range(maxiter):
        if abs(b - a) < xtol:
            return (a + b) / 2
        if abs(fb - fa) < 1e-18:
            c = (a + b) / 2
        else:
            c = b - fb * (b - a) / (fb - fa)
            if c <= min(a, b) or c >= max(a, b):
                c = (a + b) / 2
        fc = f(c)
        if abs(fc) < xtol:
            return c
        if fa * fc < 0:
            b, fb = c, fc
        else:
            a, fa = c, fc
    return (a + b) / 2


def xirr(cash_flows: list[float], dates: list[date]) -> Optional[float]:
    """Annualised IRR (%) solving Σ CF/(1+r)^t = 0."""
    if len(cash_flows) < 2 or len(cash_flows) != len(dates):
        return None
    d0 = dates[0]
    t = [(d - d0).days / 365.25 for d in dates]

    def npv(r: float) -> float:
        return sum(cf / (1 + r) ** ti for cf, ti in zip(cash_flows, t))

    try:
        return round(brent_root(npv, -0.9999, 10.0) * 100, 2)
    except Exception:
        return None


def absolute_return_pct(invested: float, current: float) -> float:
    if invested <= 0:
        return 0.0
    return round((current - invested) / invested * 100, 2)


def hhi(weights: list[float]) -> float:
    return round(sum(w * w for w in weights), 4)


def jaccard(a: list, b: list) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def risk_capacity(
    drop_response: str,
    income_stability: str = "medium",
    experience: str = "medium",
) -> int:
    drop_map = {
        "sell": 10,
        "hold": 45,
        "buy": 85,
        "conservative": 20,
        "moderate": 50,
        "aggressive": 80,
        "very aggressive": 95,
    }
    stab = {"low": 25, "medium": 55, "high": 80}
    exp = {"low": 25, "medium": 55, "high": 80}
    score = (
        0.5 * drop_map.get(drop_response.lower(), 50)
        + 0.3 * stab.get(income_stability.lower(), 55)
        + 0.2 * exp.get(experience.lower(), 55)
    )
    return int(round(score))


def risk_bucket(capacity: int) -> str:
    if capacity < 35:
        return "conservative"
    if capacity < 65:
        return "balanced"
    return "aggressive"


def required_return_pct(
    target: float, lumpsum: float, monthly_sip: float, years: float
) -> Optional[float]:
    if years <= 0 or target <= 0:
        return None
    if lumpsum <= 0 and monthly_sip <= 0:
        return None

    def fv(r_annual: float) -> float:
        if abs(r_annual) < 1e-9:
            return lumpsum + monthly_sip * years * 12
        rm = r_annual / 12
        n = years * 12
        sip_fv = (
            monthly_sip * (((1 + rm) ** n - 1) / rm) if monthly_sip and abs(rm) > 1e-12 else monthly_sip * n
        )
        lump_fv = lumpsum * ((1 + r_annual) ** years) if lumpsum else 0
        return lump_fv + sip_fv

    if fv(0.0) >= target:
        return 0.0
    if fv(0.30) < target * 0.98:
        return 30.01

    def gap(r: float) -> float:
        return fv(r) - target

    try:
        r = brent_root(gap, 0.0, 0.30, maxiter=200)
        return round(max(0.0, r) * 100, 2)
    except Exception:
        lo, hi = 0.0, 0.30
        for _ in range(80):
            mid = (lo + hi) / 2
            if gap(mid) >= 0:
                hi = mid
            else:
                lo = mid
        return round(hi * 100, 2)


def fd_accrued(principal: float, rate_pct: float, years: float) -> float:
    r = rate_pct / 100
    return round(principal * (1 + r / 4) ** (4 * years), 2)


def parse_date(s: str) -> date:
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except Exception:
        return date(2021, 1, 1)
