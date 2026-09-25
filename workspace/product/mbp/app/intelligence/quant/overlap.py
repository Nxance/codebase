"""L1 — holdings overlap (Jaccard)."""
from __future__ import annotations

from .metrics import jaccard

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


def fund_key(name: str) -> str | None:
    n = name.lower()
    for key in HOLDINGS_DB:
        if key in n or all(w in n for w in key.split() if len(w) > 3):
            return key
    return None


def pairwise_overlap(mf_holdings: list[dict]) -> tuple[float, list[dict]]:
    pairs = []
    waste = 0.0
    for i in range(len(mf_holdings)):
        for j in range(i + 1, len(mf_holdings)):
            a, b = mf_holdings[i], mf_holdings[j]
            ka, kb = fund_key(a["name"]), fund_key(b["name"])
            if not ka or not kb:
                continue
            jac = jaccard(HOLDINGS_DB[ka], HOLDINGS_DB[kb])
            if jac > 0.15:
                smaller = min(a["current_value"], b["current_value"])
                w = round(smaller * jac * 0.008, 2)
                waste += w
                pairs.append(
                    {
                        "fund_a": a["name"],
                        "fund_b": b["name"],
                        "overlap_pct": round(jac * 100, 1),
                        "annual_waste_rs": w,
                        "severity": "high" if jac > 0.5 else "medium" if jac > 0.3 else "low",
                        "common_stocks": sorted(
                            set(HOLDINGS_DB[ka]) & set(HOLDINGS_DB[kb])
                        )[:8],
                        "method": "jaccard_holdings",
                        "layer": "L1_quant",
                    }
                )
    pairs.sort(key=lambda x: x["overlap_pct"], reverse=True)
    return round(waste, 2), pairs
