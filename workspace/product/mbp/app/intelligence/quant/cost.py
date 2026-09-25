"""L1 — cost / TER leakage."""
from __future__ import annotations

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


def get_ter(name: str, plan: str) -> float:
    n = name.lower()
    db = TER.get(plan, TER["regular"])
    for key, val in db.items():
        if key != "default" and key in n:
            return val
    return db["default"]


def ter_waste(holdings: list[dict]) -> tuple[float, list[dict]]:
    """Annual ₹ leak from Regular vs Direct on MF holdings."""
    total = 0.0
    detail = []
    for h in holdings:
        if h.get("asset_class") != "mutual_fund":
            continue
        if h.get("plan_type") != "regular":
            continue
        reg = get_ter(h["name"], "regular")
        direct = get_ter(h["name"], "direct")
        waste = round(float(h["current_value"]) * (reg - direct) / 100, 2)
        if waste > 0:
            total += waste
            detail.append(
                {
                    "fund": h["name"],
                    "regular_ter": reg,
                    "direct_ter": direct,
                    "annual_waste_rs": waste,
                    "layer": "L1_quant",
                }
            )
    return round(total, 2), detail
