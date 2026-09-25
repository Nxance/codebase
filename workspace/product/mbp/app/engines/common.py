"""Shared maths, AMFI helpers, TER/holdings DBs for MBP engines."""
from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def brentq(f, a: float, b: float, maxiter: int = 1000, xtol: float = 1e-6) -> float:
    """Pure-Python Brent-style root finder (no scipy — zero build deps)."""
    fa, fb = f(a), f(b)
    if fa * fb > 0:
        raise ValueError("Root not bracketed")
    for _ in range(maxiter):
        if abs(b - a) < xtol:
            return (a + b) / 2
        # Secant step with bisection fallback
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

_cache: dict[str, Any] = {}
_cache_ts: dict[str, datetime] = {}
CACHE_HOURS = 6

# ── TER (AMFI-style defaults for MBP) ─────────────────────────────
TER = {
    "regular": {
        "default": 1.55,
        "axis bluechip": 1.54,
        "mirae large": 1.52,
        "sbi blue": 1.62,
        "hdfc flexi": 1.68,
        "hdfc top": 1.68,
        "parag parikh": 1.71,
        "icici pru bluechip": 1.56,
        "nifty 50": 0.20,
        "uti nifty": 0.18,
        "axis midcap": 1.88,
        "sbi small": 1.73,
        "kotak": 1.62,
    },
    "direct": {
        "default": 0.50,
        "axis bluechip": 0.47,
        "mirae large": 0.52,
        "sbi blue": 0.83,
        "hdfc flexi": 0.98,
        "hdfc top": 0.98,
        "parag parikh": 0.66,
        "icici pru bluechip": 0.98,
        "nifty 50": 0.10,
        "uti nifty": 0.10,
        "axis midcap": 0.55,
        "sbi small": 0.70,
        "kotak": 0.62,
    },
}

HOLDINGS_DB = {
    "axis bluechip": [
        "HDFC Bank", "Infosys", "Reliance", "ICICI Bank", "TCS", "Kotak MB",
        "Bajaj Finance", "HUL", "Asian Paints", "Maruti",
    ],
    "mirae large": [
        "HDFC Bank", "Infosys", "Reliance", "ICICI Bank", "TCS", "Kotak MB",
        "Axis Bank", "L&T", "Bharti Airtel", "ITC",
    ],
    "sbi blue": [
        "HDFC Bank", "Infosys", "ICICI Bank", "Reliance", "TCS", "L&T",
        "Kotak MB", "Axis Bank", "HUL", "ITC",
    ],
    "hdfc flexi": [
        "HDFC Bank", "ICICI Bank", "Infosys", "Reliance", "Axis Bank",
        "Bharti Airtel", "SBI", "ITC", "Kotak MB", "L&T",
    ],
    "hdfc top": [
        "HDFC Bank", "Infosys", "Reliance", "ICICI Bank", "TCS",
        "Axis Bank", "L&T", "Kotak MB", "HUL", "Bharti Airtel",
    ],
    "icici pru bluechip": [
        "HDFC Bank", "Infosys", "Reliance", "ICICI Bank", "TCS",
        "L&T", "Kotak MB", "HUL", "Axis Bank", "ITC",
    ],
    "parag parikh": [
        "HDFC Bank", "Infosys", "ITC", "Axis Bank", "HCL Tech",
        "Coal India", "Power Grid", "Maruti", "HUL", "ICICI Bank",
    ],
    "nifty 50": [
        "HDFC Bank", "Infosys", "Reliance", "ICICI Bank", "TCS",
        "Kotak MB", "HUL", "Axis Bank", "L&T", "Bajaj Finance",
    ],
    "uti nifty": [
        "HDFC Bank", "Infosys", "Reliance", "ICICI Bank", "TCS",
        "Kotak MB", "HUL", "Axis Bank", "L&T", "Bajaj Finance",
    ],
    "axis midcap": [
        "Persistent", "Coforge", "Mphasis", "KPIT Tech", "Dixon Tech",
        "Voltas", "PI Ind", "Alkem Lab", "Cholamandalam", "Trent",
    ],
    "sbi small": [
        "Blue Star", "Techno Elec", "KEI Ind", "Lemon Tree", "Safari Ind",
        "CAMS", "Polycab", "Astral", "Crompton", "Fine Org",
    ],
}

BENCH = {
    "Nifty 50": 14.5,
    "Nifty 500": 15.2,
    "Category Avg MF": 12.8,
    "SBI FD (5yr)": 7.1,
}

# Basic SEBI/AMFI-style name whitelist fragments for fraud gate
LEGIT_FRAGMENTS = [
    "hdfc", "sbi", "icici", "axis", "kotak", "mirae", "parag", "uti",
    "nippon", "aditya", "franklin", "dsp", "tata", "motilal", "quant",
    "reliance", "infosys", "tcs", "bharti", "titan", "asian paints",
    "fd", "fixed deposit", "post office", "nifty", "sensex", "bank",
]


def cache_fresh(key: str) -> bool:
    if key not in _cache_ts:
        return False
    return (datetime.now() - _cache_ts[key]).total_seconds() < CACHE_HOURS * 3600


def amfi_fund(scheme_code: str) -> dict:
    key = f"fund_{scheme_code}"
    if cache_fresh(key):
        return _cache[key]
    try:
        r = requests.get(f"https://api.mfapi.in/mf/{scheme_code}", timeout=10)
        if r.status_code == 200:
            data = r.json()
            _cache[key] = data
            _cache_ts[key] = datetime.now()
            return data
    except Exception as e:
        print(f"AMFI error {scheme_code}: {e}")
    return {}


def amfi_search(query: str) -> list:
    try:
        r = requests.get(
            "https://api.mfapi.in/mf/search", params={"q": query}, timeout=8
        )
        if r.status_code == 200:
            return r.json()[:10]
    except Exception:
        pass
    return []


def get_live_nav(scheme_code: str) -> Optional[float]:
    data = amfi_fund(scheme_code)
    navs = data.get("data", [])
    if navs:
        return float(navs[0]["nav"])
    return None


def get_nav_on_date(scheme_code: str, target: date) -> Optional[float]:
    data = amfi_fund(scheme_code)
    navs = data.get("data", [])
    for entry in reversed(navs):
        try:
            d = datetime.strptime(entry["date"], "%d-%m-%Y").date()
            if d <= target:
                return float(entry["nav"])
        except Exception:
            continue
    return None


def xirr_calc(cash_flows: list, dates: list) -> Optional[float]:
    if len(cash_flows) < 2:
        return None
    d0 = dates[0]
    t = [(d - d0).days / 365.25 for d in dates]

    def npv(r: float) -> float:
        return sum(cf / (1 + r) ** ti for cf, ti in zip(cash_flows, t))

    try:
        result = brentq(npv, -0.9999, 10.0, maxiter=1000, xtol=1e-6)
        return round(result * 100, 2)
    except Exception:
        return None


def holding_xirr(
    invested: float,
    current_value: float,
    purchase_date_str: str,
    units: Optional[float] = None,
    scheme_code: Optional[str] = None,
) -> dict:
    result = {
        "xirr": None,
        "current_value": current_value,
        "nav_live": False,
        "current_nav": None,
        "purchase_nav": None,
    }
    try:
        pdate = datetime.strptime(purchase_date_str[:10], "%Y-%m-%d").date()
    except Exception:
        pdate = date(2021, 1, 1)

    if scheme_code and units:
        current_nav = get_live_nav(scheme_code)
        purchase_nav = get_nav_on_date(scheme_code, pdate)
        if current_nav and purchase_nav and purchase_nav > 0:
            cv = round(units * current_nav, 2)
            ai = round(units * purchase_nav, 2)
            result.update(
                {
                    "current_value": cv,
                    "current_nav": current_nav,
                    "purchase_nav": purchase_nav,
                    "nav_live": True,
                }
            )
            result["xirr"] = xirr_calc([-ai, cv], [pdate, date.today()])
            return result

    if invested > 0 and current_value > 0:
        result["xirr"] = xirr_calc(
            [-invested, current_value], [pdate, date.today()]
        )
    return result


def get_ter(name: str, plan: str) -> float:
    n = name.lower()
    db = TER.get(plan, TER["regular"])
    for key, val in db.items():
        if key != "default" and key in n:
            return val
    return db["default"]


def fund_key(name: str) -> Optional[str]:
    n = name.lower()
    for key in HOLDINGS_DB:
        if key in n or all(w in n for w in key.split() if len(w) > 3):
            return key
    return None


def jaccard(a: list, b: list) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def hhi(weights: list[float]) -> float:
    return round(sum(w * w for w in weights), 4)


def load_json(name: str) -> Any:
    path = DATA_DIR / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def risk_capacity(drop_response: str, income_stability: str = "medium", experience: str = "medium") -> int:
    """0–100 risk capacity score (MBP formula slice)."""
    drop_map = {
        "sell": 10,
        "hold": 45,
        "buy": 85,
        "conservative": 20,
        "moderate": 50,
        "aggressive": 80,
        "very aggressive": 95,
    }
    stab_map = {"low": 25, "medium": 55, "high": 80}
    exp_map = {"low": 25, "medium": 55, "high": 80}
    score = (
        0.5 * drop_map.get(drop_response.lower(), 50)
        + 0.3 * stab_map.get(income_stability.lower(), 55)
        + 0.2 * exp_map.get(experience.lower(), 55)
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
    """Solve r such that FV(lumpsum)+FV(SIP) ≈ target. Returns annual %."""
    if years <= 0 or target <= 0:
        return None
    if lumpsum <= 0 and monthly_sip <= 0:
        return None

    def fv(r_annual: float) -> float:
        # r_annual as decimal
        if abs(r_annual) < 1e-9:
            sip_fv = monthly_sip * years * 12
            return lumpsum + sip_fv
        rm = r_annual / 12
        n = years * 12
        if abs(rm) < 1e-12:
            sip_fv = monthly_sip * n
        else:
            sip_fv = monthly_sip * (((1 + rm) ** n - 1) / rm) if monthly_sip else 0
        lump_fv = lumpsum * ((1 + r_annual) ** years) if lumpsum else 0
        return lump_fv + sip_fv

    # Already reaches target at 0% growth
    if fv(0.0) >= target:
        return 0.0

    # Infeasible if even 30% can't hit
    if fv(0.30) < target * 0.98:
        return 30.01  # signal infeasible

    def gap(r: float) -> float:
        return fv(r) - target

    try:
        r = brentq(gap, 0.0, 0.30, maxiter=200)
        return round(max(0.0, r) * 100, 2)
    except Exception:
        # pure bisection fallback
        lo, hi = 0.0, 0.30
        for _ in range(80):
            mid = (lo + hi) / 2
            if gap(mid) >= 0:
                hi = mid
            else:
                lo = mid
        return round(hi * 100, 2)


def fd_accrued(principal: float, rate_pct: float, years: float) -> float:
    """Quarterly compounding A = P(1+r/4)^(4t)."""
    r = rate_pct / 100
    return round(principal * (1 + r / 4) ** (4 * years), 2)


def extract_numbers(text: str) -> set[str]:
    """Digits/number tokens for Number Guard."""
    import re

    found = set(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text.replace("₹", "")))
    # also plain digit groups without commas
    for n in re.findall(r"\d+\.?\d*", text):
        found.add(n)
    return found


def flatten_numbers(obj: Any, out: Optional[set] = None) -> set[str]:
    if out is None:
        out = set()
    if isinstance(obj, dict):
        for v in obj.values():
            flatten_numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            flatten_numbers(v, out)
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, int):
        out.add(str(obj))
        out.add(f"{obj:,}")
    elif isinstance(obj, float):
        out.add(str(obj))
        out.add(f"{obj:.2f}")
        out.add(f"{obj:.1f}")
        out.add(f"{obj:.0f}")
        if abs(obj) >= 1000:
            out.add(f"{obj:,.0f}")
            out.add(f"{obj:,.2f}")
    elif isinstance(obj, str):
        out |= extract_numbers(obj)
    return out
