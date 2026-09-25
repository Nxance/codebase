#!/usr/bin/env python3
"""
Generate multivariate synthetic India portfolios for training.

Outputs:
  data/synthetic/portfolios_train.jsonl
  data/synthetic/portfolios_val.jsonl
  data/synthetic/features_train.csv
  data/synthetic/features_val.csv
  data/synthetic/labels_meta.json

Each portfolio follows india_portfolio_v1 + training labels for:
  - fund/lot quality
  - portfolio health grade
  - has_ter_leak, has_overlap, high_concentration, tax_inefficient
"""
from __future__ import annotations

import csv
import json
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.intelligence.quant.india_metrics import compute_india_portfolio_metrics
from app.intelligence.quant.cost import get_ter
from app.intelligence.quant.overlap import pairwise_overlap, fund_key
from app.intelligence.quant.metrics import hhi, xirr
from datetime import datetime

OUT = ROOT / "data" / "synthetic"
INDIA = ROOT / "data" / "india"
RNG = random.Random(42)

# Load AMFI seeds if present
def load_amfi_seeds() -> list[dict]:
    p = INDIA / "amfi_seed_funds.json"
    if p.exists():
        return json.loads(p.read_text())
    return []


SECTORS = [
    "Financials", "IT", "Energy", "Consumer", "Pharma", "Auto", "Infra", "Metals", "Telecom"
]
CAP = ["large", "mid", "small", "multi"]

MF_TEMPLATES = [
    {"name": "Axis Bluechip", "asset_class": "mutual_fund_equity", "cap": "large", "sector": "Financials", "key": "axis bluechip"},
    {"name": "Mirae Asset Large Cap", "asset_class": "mutual_fund_equity", "cap": "large", "sector": "Financials", "key": "mirae large"},
    {"name": "HDFC Flexi Cap", "asset_class": "mutual_fund_equity", "cap": "multi", "sector": "Financials", "key": "hdfc flexi"},
    {"name": "Parag Parikh Flexi Cap", "asset_class": "mutual_fund_equity", "cap": "multi", "sector": "IT", "key": "parag parikh"},
    {"name": "UTI Nifty 50 Index", "asset_class": "mutual_fund_index", "cap": "large", "sector": "Financials", "key": "uti nifty"},
    {"name": "Axis Midcap", "asset_class": "mutual_fund_equity", "cap": "mid", "sector": "Consumer", "key": "axis midcap"},
    {"name": "SBI Small Cap", "asset_class": "mutual_fund_equity", "cap": "small", "sector": "Industrials", "key": "sbi small"},
    {"name": "ICICI Pru Bluechip", "asset_class": "mutual_fund_equity", "cap": "large", "sector": "Energy", "key": "icici pru bluechip"},
    {"name": "HDFC Short Term Debt", "asset_class": "mutual_fund_debt", "cap": "na", "sector": "Debt", "key": "debt"},
    {"name": "Mirae ELSS Tax Saver", "asset_class": "mutual_fund_elss", "cap": "multi", "sector": "Financials", "key": "mirae large"},
]

STOCKS = [
    ("Reliance Industries", "RELIANCE", "Energy", "large"),
    ("HDFC Bank", "HDFCBANK", "Financials", "large"),
    ("Infosys", "INFY", "IT", "large"),
    ("TCS", "TCS", "IT", "large"),
    ("Titan", "TITAN", "Consumer", "large"),
    ("Persistent Systems", "PERSISTENT", "IT", "mid"),
]

FD_BANK = ["SBI FD 3yr", "HDFC FD 5yr", "ICICI FD 1yr", "Post Office TD 5yr"]


def daterand(years_ago_min=0.3, years_ago_max=8) -> str:
    days = int(RNG.uniform(years_ago_min, years_ago_max) * 365)
    return (date.today() - timedelta(days=days)).isoformat()


def gen_lot_mf(template: dict, plan: str, aum: float, amfi: list) -> dict:
    name = f"{template['name']} {'Direct' if plan == 'direct' else 'Regular'}"
    # map amfi code loosely
    code = None
    for a in amfi:
        sn = (a.get("schemeName") or "").lower()
        if template["key"].split()[0] in sn and ("direct" in sn) == (plan == "direct"):
            code = str(a.get("schemeCode"))
            break
    # simulate performance: regular slightly worse on net due to TER (reflected in value)
    years = RNG.uniform(0.5, 7)
    ret = RNG.gauss(0.12 if template["cap"] != "small" else 0.15, 0.08)
    invested = aum
    # net of cost drag for regular
    ter = get_ter(name, plan)
    net_ret = ret - (ter / 100) * 0.5
    value = invested * ((1 + net_ret) ** years)
    units = round(value / RNG.uniform(40, 200), 3)
    avg = round(invested / max(units, 0.001), 4)
    return {
        "lot_id": f"mf_{RNG.randrange(10**8)}",
        "asset_class": template["asset_class"],
        "name": name,
        "isin": None,
        "amfi_code": code,
        "symbol": None,
        "exchange": None,
        "folio": f"{RNG.randint(10000000, 99999999)}/{RNG.randint(0, 9)}",
        "plan_type": plan,
        "option": "growth",
        "quantity": units,
        "avg_cost": avg,
        "invested_amount": round(invested, 2),
        "current_nav_or_price": round(value / max(units, 0.001), 4),
        "current_value": round(value, 2),
        "purchase_date": daterand(years, years + 0.2),
        "maturity_date": None,
        "coupon_or_rate": None,
        "sector": template["sector"],
        "market_cap_bucket": template["cap"],
        "tax_bucket": None,
        "lock_in_until": None,
        "true_cagr": round(net_ret * 100, 2),
        "true_ter": ter,
    }


def gen_lot_stock(aum: float) -> dict:
    name, sym, sec, cap = RNG.choice(STOCKS)
    years = RNG.uniform(0.4, 6)
    ret = RNG.gauss(0.11, 0.12)
    invested = aum
    value = invested * ((1 + ret) ** years)
    qty = max(1, int(invested / RNG.uniform(500, 3000)))
    avg = invested / qty
    price = value / qty
    return {
        "lot_id": f"eq_{RNG.randrange(10**8)}",
        "asset_class": "equity_stock",
        "name": name,
        "isin": f"INE{RNG.randint(100,999)}A01018",
        "amfi_code": None,
        "symbol": sym,
        "exchange": "NSE",
        "folio": None,
        "plan_type": "na",
        "option": "na",
        "quantity": qty,
        "avg_cost": round(avg, 2),
        "invested_amount": round(invested, 2),
        "current_nav_or_price": round(price, 2),
        "current_value": round(value, 2),
        "purchase_date": daterand(years, years + 0.3),
        "maturity_date": None,
        "coupon_or_rate": None,
        "sector": sec,
        "market_cap_bucket": cap,
        "tax_bucket": None,
        "true_cagr": round(ret * 100, 2),
        "true_ter": 0.0,
    }


def gen_lot_fd(aum: float) -> dict:
    name = RNG.choice(FD_BANK)
    rate = RNG.choice([6.5, 6.8, 7.0, 7.1, 7.5])
    years = RNG.uniform(0.5, 4)
    invested = aum
    value = invested * ((1 + rate / 100 / 4) ** (4 * years))
    return {
        "lot_id": f"fd_{RNG.randrange(10**8)}",
        "asset_class": "fd",
        "name": name,
        "isin": None,
        "amfi_code": None,
        "symbol": None,
        "exchange": None,
        "folio": None,
        "plan_type": "na",
        "option": "na",
        "quantity": 1,
        "avg_cost": invested,
        "invested_amount": round(invested, 2),
        "current_nav_or_price": None,
        "current_value": round(value, 2),
        "purchase_date": daterand(years, years + 0.1),
        "maturity_date": (date.today() + timedelta(days=int((5 - years) * 365))).isoformat(),
        "coupon_or_rate": rate,
        "sector": "Debt",
        "market_cap_bucket": "na",
        "true_cagr": rate,
        "true_ter": 0.0,
    }


def gen_cashflows(lots: list[dict]) -> list[dict]:
    cfs = []
    for l in lots:
        if "mutual_fund" in l["asset_class"] and RNG.random() < 0.6:
            # synthetic monthly SIPs
            start = datetime.strptime(l["purchase_date"], "%Y-%m-%d").date()
            months = min(24, max(3, int((date.today() - start).days / 30)))
            sip_amt = -round(l["invested_amount"] / months, 0)
            for m in range(months):
                d = start + timedelta(days=30 * m)
                cfs.append(
                    {
                        "date": d.isoformat(),
                        "amount": sip_amt,
                        "type": "sip",
                        "lot_id": l["lot_id"],
                    }
                )
    return cfs


def portfolio_labels(lots: list[dict], india_m: dict) -> dict:
    """Ground-truth labels for supervised learning."""
    mf = [
        {
            "name": l["name"],
            "current_value": l["current_value"],
            "asset_class": "mutual_fund",
            "plan_type": l.get("plan_type") or "regular",
        }
        for l in lots
        if "mutual_fund" in l["asset_class"]
    ]
    # TER waste approx
    ter_waste = 0.0
    for l in lots:
        if l.get("plan_type") == "regular" and "mutual_fund" in l["asset_class"]:
            reg = get_ter(l["name"], "regular")
            d = get_ter(l["name"], "direct")
            ter_waste += l["current_value"] * (reg - d) / 100

    ovlp_w, pairs = pairwise_overlap(
        [
            {
                "name": l["name"],
                "current_value": l["current_value"],
                "asset_class": "mutual_fund",
            }
            for l in lots
            if "mutual_fund" in l["asset_class"]
        ]
    )
    total = india_m["total_value"] or 1
    weights = [l["current_value"] / total for l in lots]
    h = hhi(weights)
    regular_pct = india_m["plan_mix"]["regular_aum_pct"]
    top_sector = india_m["sector"]["top_sector_pct"]
    liquid = india_m["liquidity"]["score_0_100"]
    tax_drag = india_m["est_tax_if_fully_sold_rs"]

    # synthetic portfolio xirr proxy from true cagr weighted
    port_xirr = sum(
        (l["current_value"] / total) * float(l.get("true_cagr") or 10) for l in lots
    )

    # health score-like label 0-100
    score = 100
    if ter_waste / total > 0.005:
        score -= 15
    if ovlp_w / total > 0.003:
        score -= 12
    if h > 0.35:
        score -= 10
    if top_sector > 45:
        score -= 8
    if port_xirr < 8:
        score -= 15
    if regular_pct > 60:
        score -= 8
    if liquid < 40:
        score -= 6
    score = max(15, min(98, score))
    if score >= 86:
        grade = "A"
    elif score >= 71:
        grade = "B"
    elif score >= 56:
        grade = "C"
    elif score >= 41:
        grade = "D"
    else:
        grade = "F"

    return {
        "label_health_score": score,
        "label_grade": grade,
        "label_has_ter_leak": int(ter_waste > 500),
        "label_has_overlap": int(len(pairs) > 0 and pairs[0]["overlap_pct"] > 30),
        "label_high_concentration": int(h > 0.35 or top_sector > 45),
        "label_tax_heavy": int(tax_drag / total > 0.08),
        "label_low_liquidity": int(liquid < 40),
        "label_port_xirr": round(port_xirr, 2),
        "y_ter_waste": round(ter_waste, 2),
        "y_overlap_waste": round(ovlp_w, 2),
        "y_hhi": h,
    }


def features_row(lots: list[dict], india_m: dict, labels: dict) -> dict:
    total = india_m["total_value"] or 1
    small = india_m["market_cap"]["cap_weights_pct"].get("small", 0)
    elss_locked = sum(
        l["current_value"]
        for l in lots
        if "elss" in l["asset_class"]
    )
    fd_pct = (
        100
        * sum(l["current_value"] for l in lots if l["asset_class"] == "fd")
        / total
    )
    days = [l.get("holding_days") or 365 for l in india_m["lots_enriched"]]
    mean_years = (sum(days) / len(days) / 365) if days else 1
    equity_pct = 100 - india_m["market_cap"]["cap_weights_pct"].get("na", 0) * 0  # rough
    # better equity %
    eq = sum(
        l["current_value"]
        for l in lots
        if any(x in l["asset_class"] for x in ("equity", "stock", "index", "elss"))
    )
    equity_pct = 100 * eq / total
    return {
        "portfolio_xirr": labels["label_port_xirr"],
        "ter_waste_pct_aum": round(100 * labels["y_ter_waste"] / total, 4),
        "overlap_waste_pct_aum": round(100 * labels["y_overlap_waste"] / total, 4),
        "hhi": labels["y_hhi"],
        "equity_pct": round(equity_pct, 2),
        "regular_aum_pct": india_m["plan_mix"]["regular_aum_pct"],
        "top_sector_pct": india_m["sector"]["top_sector_pct"],
        "smallcap_pct": small,
        "liquid_pct": india_m["liquidity"]["liquid_pct"],
        "est_tax_drag_pct_aum": round(100 * india_m["est_tax_if_fully_sold_rs"] / total, 4),
        "n_lots": india_m["n_lots"],
        "sip_regularity": india_m["sip"]["regularity_score"],
        "elss_locked_pct": round(100 * elss_locked / total, 2),
        "fd_pct": round(fd_pct, 2),
        "mean_holding_years": round(mean_years, 2),
        **{k: labels[k] for k in labels if k.startswith("label_")},
    }


def gen_portfolio(i: int, amfi: list, channel: str) -> dict:
    # persona archetypes
    archetype = RNG.choice(
        [
            "regular_overlap_heavy",  # toxic sample style
            "direct_index_clean",
            "aggressive_smallcap",
            "conservative_fd_debt",
            "mixed_tax_messy",
            "concentrated_stock",
        ]
    )
    n_mf = RNG.randint(2, 6)
    n_stock = RNG.randint(0, 3)
    n_fd = RNG.randint(0, 2)
    base_aum = RNG.uniform(80_000, 2_500_000)

    lots = []
    templates = MF_TEMPLATES.copy()
    RNG.shuffle(templates)

    if archetype == "regular_overlap_heavy":
        # force overlapping large caps regular
        for t in templates[:3]:
            if t["cap"] in ("large", "multi"):
                lots.append(gen_lot_mf(t, "regular", base_aum * RNG.uniform(0.15, 0.3), amfi))
        n_mf = 0
    elif archetype == "direct_index_clean":
        t = next(x for x in templates if "Index" in x["name"] or "index" in x["asset_class"])
        lots.append(gen_lot_mf(t, "direct", base_aum * 0.7, amfi))
        lots.append(gen_lot_mf(next(x for x in templates if "debt" in x["key"] or "Debt" in x["name"]), "direct", base_aum * 0.2, amfi))
        n_mf = 0
        n_stock = 0
    elif archetype == "aggressive_smallcap":
        for t in templates:
            if t["cap"] in ("small", "mid"):
                lots.append(gen_lot_mf(t, RNG.choice(["direct", "regular"]), base_aum * 0.25, amfi))
        n_mf = max(0, n_mf - 2)
    elif archetype == "conservative_fd_debt":
        lots.append(gen_lot_fd(base_aum * 0.4))
        lots.append(gen_lot_mf(next(x for x in templates if "debt" in x["key"] or "Debt" in x["name"]), "direct", base_aum * 0.4, amfi))
        n_mf = 1
        n_stock = 0
        n_fd = 0
    elif archetype == "concentrated_stock":
        lots.append(gen_lot_stock(base_aum * 0.55))
        n_stock = 1

    for j in range(n_mf):
        t = templates[j % len(templates)]
        plan = "regular" if archetype in ("regular_overlap_heavy", "mixed_tax_messy") and RNG.random() < 0.7 else RNG.choice(["direct", "regular"])
        lots.append(gen_lot_mf(t, plan, base_aum * RNG.uniform(0.08, 0.22), amfi))
    for _ in range(n_stock):
        lots.append(gen_lot_stock(base_aum * RNG.uniform(0.05, 0.15)))
    for _ in range(n_fd):
        lots.append(gen_lot_fd(base_aum * RNG.uniform(0.05, 0.2)))

    cashflows = gen_cashflows(lots)
    # strip training-only fields from public lots copy
    public_lots = []
    for l in lots:
        pl = {k: v for k, v in l.items() if not k.startswith("true_")}
        public_lots.append(pl)

    india_m = compute_india_portfolio_metrics(public_lots, cashflows)
    labels = portfolio_labels(lots, india_m)
    feats = features_row(lots, india_m, labels)

    doc = {
        "schema_version": "india_portfolio_v1",
        "source": {
            "channel": channel,
            "format": "json",
            "provider": "nxance_synthetic",
            "parse_confidence": 1.0,
        },
        "as_of": date.today().isoformat(),
        "currency": "INR",
        "holder": {
            "name": f"Synthetic User {i}",
            "pan_masked": "ABCDE****F",
            "phone_masked": "98******10",
            "demat_ids": [f"IN{RNG.randint(100000,999999)}"],
        },
        "lots": public_lots,
        "cashflows": cashflows,
        "goals": [
            {
                "name": RNG.choice(["Retirement", "House", "Wealth", "Education"]),
                "target_amount": round(base_aum * RNG.uniform(2, 8), 0),
                "target_date": (date.today() + timedelta(days=365 * RNG.randint(5, 20))).isoformat(),
                "priority": 1,
            }
        ],
        "meta": {
            "tax_residency": "IN",
            "risk_self": RNG.choice(["conservative", "moderate", "aggressive"]),
            "archetype": archetype,
            "training_id": f"syn_{i:05d}",
        },
        "labels": labels,
        "features": feats,
        "india_metrics": {
            k: v
            for k, v in india_m.items()
            if k != "lots_enriched"
        },
    }
    return doc


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main(n_train: int = 800, n_val: int = 200):
    OUT.mkdir(parents=True, exist_ok=True)
    amfi = load_amfi_seeds()
    channels = [
        "synthetic_training",
        "cas_cams",
        "cas_cdsl",
        "broker_zerodha",
        "broker_groww",
        "csv_upload",
        "ocr_pdf",
    ]

    train, val = [], []
    for i in range(n_train):
        train.append(gen_portfolio(i, amfi, RNG.choice(channels)))
    for i in range(n_val):
        val.append(gen_portfolio(10_000 + i, amfi, RNG.choice(channels)))

    def dump_jsonl(path: Path, rows: list):
        with path.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, default=str) + "\n")

    dump_jsonl(OUT / "portfolios_train.jsonl", train)
    dump_jsonl(OUT / "portfolios_val.jsonl", val)
    write_csv(OUT / "features_train.csv", [r["features"] for r in train])
    write_csv(OUT / "features_val.csv", [r["features"] for r in val])

    meta = {
        "n_train": n_train,
        "n_val": n_val,
        "schema": "india_portfolio_v1",
        "feature_columns": [k for k in train[0]["features"] if not k.startswith("label_")],
        "label_columns": [k for k in train[0]["features"] if k.startswith("label_")],
        "archetypes": sorted({r["meta"]["archetype"] for r in train}),
        "amfi_seeds": len(amfi),
        "generated_on": date.today().isoformat(),
        "notes": "Multivariate synthetic India portfolios for L2 training; replace with real anonymised CAS over time.",
    }
    (OUT / "labels_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    print("Wrote", OUT)


if __name__ == "__main__":
    n_train = int(sys.argv[1]) if len(sys.argv) > 1 else 800
    n_val = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    main(n_train, n_val)
