"""
Construction orchestration.

L1 profile → L4 allocation → L2 score universe → L3 diversify → L4 weights → fraud → L1 projection
"""
from __future__ import annotations

from typing import Any

from app.engines.fraud import run_fraud_gate
from app.intelligence.optimize.allocation import strategic_allocation
from app.intelligence.optimize.select import select_instruments
from app.intelligence.optimize.weights import apply_caps, mean_variance_lite
from app.intelligence.quant.metrics import required_return_pct, risk_bucket, risk_capacity
from app.intelligence.quant.projection import projection_range, monte_carlo_goal_probability

STACK = ["L1_quant", "L2_ml", "L3_dl", "L4_optimize", "L5_nlp"]


def run_construction_pipeline(questionnaire: dict, unlocked: bool = False) -> dict[str, Any]:
    goal = questionnaire.get("goal") or "Wealth Creation"
    target = float(questionnaire.get("target_amount") or 0)
    years = float(questionnaire.get("years") or 10)
    lumpsum = float(
        questionnaire.get("lumpsum") or questionnaire.get("existing_savings") or 0
    )
    sip = float(questionnaire.get("monthly_sip") or 0)
    risk_resp = str(questionnaire.get("risk") or questionnaire.get("risk_response") or "moderate")

    # L1 profile
    capacity = risk_capacity(risk_resp)
    bucket = risk_bucket(capacity)
    req = required_return_pct(target, lumpsum, sip, years) if target else None
    profile = {
        "goal": goal,
        "target_amount": target,
        "years": years,
        "lumpsum": lumpsum,
        "monthly_sip": sip,
        "risk_capacity": capacity,
        "risk_bucket": bucket,
        "required_return_pct": req,
        "infeasible": req is not None and req > 30,
        "notes": (
            "Target needs >30%/yr — increase SIP, extend years, or lower target."
            if req is not None and req > 30
            else "Required return within realistic diversified band."
        ),
        "layer": "L1_quant",
    }

    # L4 strategic allocation
    allocation = strategic_allocation(
        years=years, risk_bucket=bucket, required_return_pct=req
    )

    # L2+L3 selection
    pool = select_instruments(
        allocation=allocation,
        risk_bucket=bucket,
        years=years,
        monthly_sip=sip,
        lumpsum=lumpsum,
    )

    # L4 weights
    class_budget = {
        "equity": allocation["allocation_pct"]["equity"],
        "debt_mf": allocation["allocation_pct"]["debt_mf"],
        "fd": allocation["allocation_pct"]["fd"],
    }
    # If stocks sleeve requested, split equity budget
    stock_share = allocation.get("stock_share_of_equity_pct") or 0
    weighted = mean_variance_lite(pool, class_budget)
    instruments = apply_caps(
        weighted, monthly_sip=sip, lumpsum=lumpsum, max_stock=15.0, max_single=40.0
    )

    # Fraud on proposed names
    pseudo = [
        {
            "name": i["name"],
            "invested_amount": i.get("lumpsum_rs") or 10000,
            "current_value": i.get("lumpsum_rs") or 10000,
            "asset_class": "mutual_fund" if i.get("type") == "mutual_fund" else i.get("type"),
            "xirr": i.get("expected_return_pct"),
        }
        for i in instruments
    ]
    fraud = run_fraud_gate(pseudo)
    if fraud["critical"]:
        instruments = [
            i
            for i in instruments
            if not any(
                f.get("holding") == i["name"] and f["severity"] == "critical"
                for f in fraud["flags"]
            )
        ]

    expected = round(
        sum(i["allocation_pct"] / 100 * float(i.get("expected_return_pct") or 10) for i in instruments),
        2,
    ) if instruments else allocation.get("expected_blended_return_pct", 10)

    proj = projection_range(lumpsum, sip, years, expected)
    mc = None
    if target and years:
        mc = monte_carlo_goal_probability(
            lumpsum, sip, years, target, mu_pct=expected, sigma_pct=14.0
        )

    types = {i.get("type") for i in instruments}
    div_ok = len(instruments) >= 3 and len(types) >= 2

    teaser = (
        f"Goal: {goal} in {years:.0f} yrs. "
        f"Mix equity {allocation['allocation_pct']['equity']}% / "
        f"debt {allocation['allocation_pct']['debt_mf']}% / "
        f"FD {allocation['allocation_pct']['fd']}%. "
        f"Optimiser expected ~{expected}%/yr (model)."
    )

    out = {
        "engine": "construction",
        "intelligence_stack": {
            "layers": STACK,
            "order": "L1_profile → L4_alloc → L2_score → L3_diversity → L4_weights → fraud → L1_project",
            "principle": "Optimiser allocates; ML ranks; DL diversifies; language explains",
        },
        "sub_engines": [
            "profile_goal_L1",
            "allocation_L4",
            "selection_L2_L3",
            "weights_L4",
            "fraud_gate",
            "projection_L1",
        ],
        "profile": profile,
        "allocation": allocation,
        "fraud": fraud,
        "expected_return_pct": expected,
        "diversification": {
            "ok": div_ok,
            "max_single_pct": max((i["allocation_pct"] for i in instruments), default=0),
            "instrument_count": len(instruments),
        },
        "projection": proj,
        "monte_carlo": mc,
        "teaser_summary": teaser,
        "summary": teaser,
        "suggestion_only": True,
        "disclaimer": (
            "Suggestion only. Weights from L4 optimiser using L2 scores + L3 diversity. "
            "Not a recommendation to buy."
        ),
        "score": min(95, 55 + len(instruments) * 5 + (10 if div_ok else 0)),
        "grade": "B" if div_ok else "C",
    }

    if unlocked:
        out["instruments"] = instruments
        out["unlocked"] = True
    else:
        out["instruments"] = [
            {
                "type": i.get("type"),
                "allocation_pct": i.get("allocation_pct"),
                "name": "Unlock to see",
                "fit_score": i.get("fit_score"),
            }
            for i in instruments[:1]
        ]
        out["locked_instrument_count"] = len(instruments)
        out["unlocked"] = False
        out["paywall"] = {
            "price_rs": 99,
            "message": "Unlock exact instruments, ₹ amounts, FIT/ML drivers.",
            "method": "UPI → unlock code",
        }
    return out
