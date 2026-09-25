"""L4 — instrument universe filter + selection using L2 scores + L3 diversity."""
from __future__ import annotations

import json
from pathlib import Path

from app.intelligence.dl.embeddings import diversify_by_embedding
from app.intelligence.ml.scorer import score_universe

DATA = Path(__file__).resolve().parents[2] / "data" / "universes.json"


def _load_universe() -> dict:
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def select_instruments(
    *,
    allocation: dict,
    risk_bucket: str,
    years: float,
    monthly_sip: float,
    lumpsum: float,
) -> list[dict]:
    uni = _load_universe()
    mfs = uni["mutual_funds"]
    stocks = uni["stocks"]
    fds = uni["fds"]

    def ok_mf(m):
        if risk_bucket == "conservative":
            return m["risk"] in ("conservative", "moderate") and m["category"] in (
                "debt", "hybrid", "index", "large",
            )
        if risk_bucket == "aggressive":
            return True
        return m["risk"] in ("conservative", "moderate") and m["category"] != "small"

    eq_mfs = [
        {**m, "type": "mutual_fund"}
        for m in mfs
        if ok_mf(m) and m["category"] not in ("debt",)
    ]
    debt_mfs = [
        {**m, "type": "mutual_fund"}
        for m in mfs
        if m["category"] in ("debt", "hybrid")
    ]
    stock_cands = [
        {
            "name": s["name"],
            "type": "stock",
            "symbol": s["symbol"],
            "category": s.get("sector", "stock"),
            "expected_return_pct": s["expected_return"],
            "ter_direct": 0.0,
            "risk": s["risk"],
            "why": f"Sector {s['sector']}; long-horizon equity sleeve.",
        }
        for s in stocks
    ]
    fd_cands = [
        {
            "name": f["name"],
            "type": "fd",
            "category": "fd",
            "expected_return_pct": f["rate"],
            "ter_direct": 0.0,
            "risk": "conservative",
            "why": f"Capital safety ~{f['rate']}%/yr; DICGC up to ₹5L/bank.",
        }
        for f in fds
    ]

    # L2 score each sleeve
    eq_scored = score_universe(eq_mfs)
    debt_scored = score_universe(debt_mfs)
    stock_scored = score_universe(stock_cands)
    fd_scored = score_universe(fd_cands)

    # L3 diversify top equity names
    eq_div = diversify_by_embedding(eq_scored, max_n=4)
    debt_div = diversify_by_embedding(debt_scored, max_n=2)
    stock_div = diversify_by_embedding(stock_scored, max_n=2) if allocation.get("stock_share_of_equity_pct", 0) > 0 else []
    fd_div = fd_scored[:2]

    # Attach why for MFs
    for m in eq_div + debt_div:
        m.setdefault(
            "why",
            f"L2 FIT {m.get('fit_score')}; Direct TER {m.get('ter_direct')}; cat {m.get('category')}.",
        )
        m["safety_ok"] = m.get("risk") != "aggressive" or years >= 7

    pool = eq_div + debt_div + stock_div + fd_div
    # Annotate selection stack
    for p in pool:
        p["selection_stack"] = ["L2_ml_score", "L3_embed_diversity", "L4_optimize"]
    return pool
