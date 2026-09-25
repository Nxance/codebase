"""
Health Check orchestration — correct layer order.

L1 measure → L2 score/anomaly → L1 fraud hard rules → guidance → L5 later in API.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.engines.common import holding_xirr
from app.engines.fraud import run_fraud_gate
from app.intelligence.ingest.canonical import engine_holdings_to_lots
from app.intelligence.ml.anomaly import anomaly_flags
from app.intelligence.ml.scorer import score_holdings
from app.intelligence.ml.trained import build_feature_dict_from_engine, predict_all
from app.intelligence.quant.cost import get_ter, ter_waste
from app.intelligence.quant.india_metrics import compute_india_portfolio_metrics
from app.intelligence.quant.metrics import (
    absolute_return_pct,
    hhi,
    required_return_pct,
    risk_bucket,
    risk_capacity,
)
from app.intelligence.quant.overlap import pairwise_overlap
from app.intelligence.quant.projection import monte_carlo_goal_probability
from app.intelligence.quant.risk import portfolio_risk_snapshot

BENCH = {
    "Nifty 50": 14.5,
    "Nifty 500": 15.2,
    "Category Avg MF": 12.8,
    "SBI FD (5yr)": 7.1,
}

STACK = ["L1_quant", "L1_quant_india", "L2_ml", "L2_ml_trained", "L3_dl", "L5_nlp"]


def _parse(raw: list[dict]) -> dict:
    clean, errors = [], []
    for i, h in enumerate(raw):
        name = str(h.get("name") or "").strip()
        if not name:
            errors.append(f"Row {i+1}: missing name")
            continue
        try:
            cv = float(h.get("current_value") or 0)
            inv = float(h.get("invested_amount") or h.get("invested") or 0)
        except Exception:
            errors.append(f"Row {i+1}: bad numbers")
            continue
        if cv <= 0 and inv <= 0:
            errors.append(f"Row {i+1}: no value")
            continue
        if cv <= 0:
            cv = inv
        plan = "direct" if "direct" in str(h.get("plan_type") or "regular").lower() else "regular"
        asset = str(h.get("asset_class") or "mutual_fund").lower()
        if asset in ("mf", "mutual fund"):
            asset = "mutual_fund"
        if asset in ("fixed_deposit", "fixed deposit"):
            asset = "fd"
        if asset not in ("mutual_fund", "stock", "fd"):
            asset = "mutual_fund"
        units = h.get("units")
        try:
            units = float(units) if units not in (None, "", "nan") else None
        except Exception:
            units = None
        scheme = h.get("scheme_code")
        scheme = str(scheme).strip() if scheme else None
        clean.append(
            {
                "name": name,
                "scheme_code": scheme,
                "current_value": cv,
                "invested_amount": inv,
                "units": units,
                "plan_type": plan,
                "purchase_date": str(h.get("purchase_date") or "2021-01-01")[:10],
                "asset_class": asset,
            }
        )
    return {"holdings": clean, "errors": errors, "count": len(clean)}


def run_health_pipeline(
    holdings_raw: list[dict],
    questionnaire: dict,
    unlocked: bool = False,
) -> dict[str, Any]:
    parsed = _parse(holdings_raw)
    if not parsed["holdings"]:
        return {"error": "No valid holdings", "parse_errors": parsed["errors"]}

    # ── L1: per-holding measurement ─────────────────────────────
    h_results = []
    total_val = total_inv = 0.0
    xirr_num = xirr_den = 0.0
    for h in parsed["holdings"]:
        xd = holding_xirr(
            h["invested_amount"],
            h["current_value"],
            h["purchase_date"],
            h.get("units"),
            h.get("scheme_code"),
        )
        cv = xd["current_value"]
        total_val += cv
        total_inv += h["invested_amount"]
        if xd["xirr"] is not None:
            xirr_num += xd["xirr"] * cv
            xirr_den += cv
        ter_val = get_ter(h["name"], h["plan_type"]) if h["asset_class"] == "mutual_fund" else 0.0
        row = {
            **h,
            "current_value": round(cv, 2),
            "return_pct": absolute_return_pct(h["invested_amount"], cv),
            "xirr": xd["xirr"],
            "ter": ter_val,
            "current_nav": xd.get("current_nav"),
            "purchase_nav": xd.get("purchase_nav"),
            "nav_live": xd.get("nav_live", False),
            "weight": 0.0,
        }
        h_results.append(row)

    if total_val > 0:
        for r in h_results:
            r["weight"] = r["current_value"] / total_val

    port_xirr = round(xirr_num / xirr_den, 2) if xirr_den > 0 else None
    total_ret = absolute_return_pct(total_inv, total_val)
    weights = [r["weight"] for r in h_results]
    concentration = hhi(weights)

    ter_w, ter_detail = ter_waste(h_results)
    mf = [r for r in h_results if r["asset_class"] == "mutual_fund"]
    ovlp_w, ovlp_pairs = pairwise_overlap(mf)

    target = float(questionnaire.get("target_amount") or 0)
    years = float(questionnaire.get("years") or 0)
    if not years and questionnaire.get("target_year"):
        years = max(0, int(questionnaire["target_year"]) - date.today().year)
    sip = float(questionnaire.get("monthly_sip") or 0)
    req = required_return_pct(target, total_val, sip, years) if target and years else None
    goal_gap = round(req - port_xirr, 2) if req is not None and port_xirr is not None else None

    drop = questionnaire.get("risk_response") or questionnaire.get("risk") or "moderate"
    capacity = risk_capacity(str(drop))
    bucket = risk_bucket(capacity)
    risk = portfolio_risk_snapshot(h_results, total_val, bucket)
    risk["risk_capacity"] = capacity
    risk["risk_bucket"] = bucket

    # Monte Carlo goal probability (L1)
    mc = None
    if target and years and port_xirr is not None:
        mc = monte_carlo_goal_probability(
            total_val, sip, years, target, mu_pct=max(port_xirr, 8.0), sigma_pct=15.0
        )

    bench_out = {}
    if port_xirr is not None:
        for bname, bval in BENCH.items():
            bench_out[bname] = {
                "return": bval,
                "difference": round(port_xirr - bval, 2),
                "verdict": "Outperforming" if port_xirr > bval else "Underperforming",
            }

    # ── L1 India-centric metrics ────────────────────────────────
    lots = engine_holdings_to_lots(h_results)
    india = compute_india_portfolio_metrics(lots, cashflows=[])

    # ── L2: quality scores + anomalies + trained bundle ─────────
    ml_scores = score_holdings(h_results, port_xirr)
    anomalies = anomaly_flags(h_results)
    score_by_name = {m["name"]: m for m in ml_scores}
    for r in h_results:
        m = score_by_name.get(r["name"])
        if m:
            r["quality_score"] = m["quality_score"]
            r["ml_drivers"] = m["drivers"]

    feat = build_feature_dict_from_engine(
        portfolio_xirr=port_xirr,
        ter_waste=ter_w,
        overlap_waste=ovlp_w,
        total_value=total_val,
        hhi_v=concentration,
        equity_pct=float(risk.get("equity_pct") or 0),
        regular_aum_pct=float(india["plan_mix"].get("regular_aum_pct") or 0),
        top_sector_pct=float(india["sector"].get("top_sector_pct") or 0),
        smallcap_pct=float(india["market_cap"]["cap_weights_pct"].get("small") or 0),
        liquid_pct=float(india["liquidity"].get("liquid_pct") or 0),
        tax_drag=float(india.get("est_tax_if_fully_sold_rs") or 0),
        n_lots=len(h_results),
        sip_regularity=float(india["sip"].get("regularity_score") or 0),
        elss_locked_pct=0.0,
        fd_pct=100.0
        * sum(1 for h in h_results if h.get("asset_class") == "fd")
        / max(1, len(h_results)),
        mean_holding_years=2.5,
    )
    trained = predict_all(feat)

    # ── L3 deep: embedding-style fund overlap (zero-cost) ──────
    from app.intelligence.dl.models import portfolio_embedding_overlap, deep_status

    deep_overlap = portfolio_embedding_overlap(h_results)

    # ── Fraud (rules, shared) ───────────────────────────────────
    fraud = run_fraud_gate(h_results)

    # ── Guidance (uses L1 economics + L2 signals) ───────────────
    issues = _guidance(
        {
            "ter_waste_annual_rs": ter_w,
            "ter_detail": ter_detail,
            "overlap_waste_annual_rs": ovlp_w,
            "overlap_pairs": ovlp_pairs,
            "deep_overlap_pairs": deep_overlap.get("pairs") or [],
            "deep_cluster_risk": deep_overlap.get("cluster_risk") or 0,
            "goal_gap_pct": goal_gap,
            "required_return_pct": req,
            "portfolio_xirr": port_xirr,
            "total_value": total_val,
            "years": years,
            "target_amount": target,
        },
        risk,
        fraud,
        anomalies,
        ml_scores,
        india,
        trained,
    )

    sc = _score(port_xirr, total_val, ter_w, ovlp_w, risk, fraud, goal_gap, mc, trained)

    free_issue = issues[0] if issues else None
    teaser = (
        f"Score {sc['score']}/100 ({sc['grade']} — {sc['grade_label']}). "
        f"Value ₹{total_val:,.0f}"
        + (f", XIRR {port_xirr}%/yr" if port_xirr is not None else "")
        + ". "
    )
    if free_issue:
        teaser += (
            f"Top issue: {free_issue['title']} "
            f"(~₹{free_issue.get('annual_cost_rs', 0):,.0f}/yr)."
        )

    full = {
        "engine": "health_check",
        "intelligence_stack": {
            "layers": STACK,
            "order": "L1_measure → L2_score → fraud → guidance → L5_explain",
            "principle": "LLM never computes; ML scores; quant measures",
        },
        **sc,
        "total_value": round(total_val, 2),
        "total_invested": round(total_inv, 2),
        "total_return_pct": total_ret,
        "portfolio_xirr": port_xirr,
        "ter_waste_annual_rs": ter_w,
        "overlap_waste_annual_rs": ovlp_w,
        "hhi": concentration,
        "required_return_pct": req,
        "goal_gap_pct": goal_gap,
        "monte_carlo": mc,
        "benchmark_comparison": bench_out,
        "risk": risk,
        "fraud": fraud,
        "india_metrics": {
            k: india[k]
            for k in india
            if k
            in (
                "sector",
                "market_cap",
                "plan_mix",
                "liquidity",
                "sip",
                "est_tax_if_fully_sold_rs",
                "unrealised_gain_rs",
                "metric_set",
                "layer",
            )
        },
        "ml": {
            "holding_scores": ml_scores if unlocked else ml_scores[:1],
            "anomalies": anomalies if unlocked else anomalies[:1],
            "backend": "weighted_linear_priors",
            "trained": trained if unlocked else {
                "available": trained.get("available"),
                "backend": trained.get("backend"),
                "predictions": {
                    k: trained.get("predictions", {}).get(k)
                    for k in ("has_ter_leak", "health_score")
                    if trained.get("predictions")
                }
                if trained.get("available")
                else {},
            },
        },
        "dl": {
            "status": deep_status(),
            "embedding_overlap": deep_overlap if unlocked else {
                "n_pairs": deep_overlap.get("n_pairs"),
                "max_similarity": deep_overlap.get("max_similarity"),
                "cluster_risk": deep_overlap.get("cluster_risk"),
                "backend": deep_overlap.get("backend"),
                "layer": "L3_dl",
                "pairs": (deep_overlap.get("pairs") or [])[:1],
            },
        },
        "parse_errors": parsed["errors"],
        "questionnaire": {
            "goal": questionnaire.get("goal"),
            "years": years,
            "target_amount": target,
            "risk": drop,
        },
        "suggestion_only": True,
        "disclaimer": (
            "Suggestion only. Not SEBI-registered investment advice. "
            "Returns measured (L1); quality scored (L2); language explains (L5)."
        ),
        "teaser_summary": teaser,
        "summary": teaser,
        "data_source": "L1 quant + live AMFI when scheme codes provided",
    }

    if unlocked:
        full["issues"] = issues
        full["holdings_detail"] = h_results
        full["ter_detail"] = ter_detail
        full["overlap_pairs"] = ovlp_pairs
        full["unlocked"] = True
    else:
        full["issues"] = [free_issue] if free_issue else []
        if full["issues"]:
            full["issues"][0]["is_free"] = True
        full["holdings_detail"] = [
            {
                "name": h["name"],
                "current_value": h["current_value"],
                "asset_class": h["asset_class"],
                "plan_type": h.get("plan_type"),
                "quality_score": h.get("quality_score"),
            }
            for h in h_results
        ]
        full["locked_issue_count"] = max(0, len(issues) - 1)
        full["unlocked"] = False
        full["paywall"] = {
            "price_rs": 99,
            "message": "Unlock full ranked fixes, ML drivers, MC bands, chat.",
            "method": "UPI → unlock code",
        }
    return full


def _guidance(analysis, risk, fraud, anomalies, ml_scores, india=None, trained=None) -> list[dict]:
    issues = []
    india = india or {}
    trained = trained or {}
    if fraud.get("critical") or fraud.get("flags"):
        for fl in fraud["flags"][:3]:
            if fl["severity"] in ("critical", "high"):
                issues.append(
                    {
                        "title": f"Fraud/Integrity: {fl['check']}",
                        "annual_cost_rs": 0,
                        "severity": fl["severity"],
                        "description": fl["message"],
                        "fix": "Verify on AMFI/SEBI/NSE before adding capital.",
                        "priority": 0,
                        "source_layers": ["fraud_rules"],
                    }
                )
    if analysis["ter_waste_annual_rs"] > 0:
        issues.append(
            {
                "title": "Regular Plan Cost Leak",
                "annual_cost_rs": analysis["ter_waste_annual_rs"],
                "severity": "high" if analysis["ter_waste_annual_rs"] > 3000 else "medium",
                "description": (
                    f"Annual TER leak ~₹{analysis['ter_waste_annual_rs']:,.0f} "
                    f"vs Direct plans (L1 quant)."
                ),
                "fix": "Switch to Direct via MF Central (mfcentral.com).",
                "detail": analysis["ter_detail"],
                "priority": 1,
                "source_layers": ["L1_quant"],
            }
        )
    if analysis["overlap_pairs"]:
        w = analysis["overlap_pairs"][0]
        issues.append(
            {
                "title": "Fund Overlap Detected",
                "annual_cost_rs": analysis["overlap_waste_annual_rs"],
                "severity": w["severity"],
                "description": (
                    f"{w['fund_a']} vs {w['fund_b']} — {w['overlap_pct']}% Jaccard overlap (L1)."
                ),
                "fix": "Replace one overlapping large-cap with a different category.",
                "detail": analysis["overlap_pairs"],
                "priority": 2,
                "source_layers": ["L1_quant"],
            }
        )
    deep_pairs = analysis.get("deep_overlap_pairs") or []
    if deep_pairs and not analysis.get("overlap_pairs"):
        # surface L3 style-similarity when L1 Jaccard is quiet
        d0 = deep_pairs[0]
        issues.append(
            {
                "title": "Style Overlap (Deep Embedding)",
                "annual_cost_rs": round(analysis["total_value"] * 0.003, 2),
                "severity": d0.get("severity", "medium"),
                "description": d0.get("message")
                or f"{d0.get('a')} ~ {d0.get('b')} (L3 embedding).",
                "fix": "Diversify style sleeves; avoid two funds that move the same way.",
                "detail": deep_pairs[:5],
                "priority": 2,
                "source_layers": ["L3_dl"],
            }
        )
    if analysis.get("goal_gap_pct") is not None and analysis["goal_gap_pct"] > 1:
        issues.append(
            {
                "title": "Goal Return Gap",
                "annual_cost_rs": 0,
                "severity": "high" if analysis["goal_gap_pct"] > 3 else "medium",
                "description": (
                    f"Required ~{analysis['required_return_pct']}%/yr vs XIRR "
                    f"{analysis['portfolio_xirr']}% (gap {analysis['goal_gap_pct']}%)."
                ),
                "fix": "Raise SIP, extend years, or improve allocation — suggestion only.",
                "priority": 3,
                "source_layers": ["L1_quant"],
            }
        )
    # L2: low quality holdings
    weak = [m for m in ml_scores if m["quality_score"] < 55]
    if weak:
        w0 = weak[0]
        issues.append(
            {
                "title": f"Low ML quality score: {w0['name']}",
                "annual_cost_rs": round(analysis["total_value"] * 0.005, 2),
                "severity": "medium",
                "description": (
                    f"L2 quality score {w0['quality_score']}/100 "
                    f"(prior-weighted model, not yet trained on live labels)."
                ),
                "fix": "Review TER, plan type, and relative XIRR; consider replacement.",
                "priority": 4,
                "source_layers": ["L2_ml"],
            }
        )
    for an in anomalies[:2]:
        issues.append(
            {
                "title": f"Anomaly: {an['type']}",
                "annual_cost_rs": 0,
                "severity": an.get("severity", "low"),
                "description": an["message"],
                "fix": "Validate data entry; outliers can be data errors or true risk.",
                "priority": 5,
                "source_layers": ["L2_ml"],
            }
        )
    if risk.get("concentrated"):
        issues.append(
            {
                "title": "High Concentration",
                "annual_cost_rs": round(analysis["total_value"] * 0.01, 2),
                "severity": "medium",
                "description": f"HHI={risk['hhi']} (L1).",
                "fix": "Add uncorrelated sleeves (different category / FD buffer).",
                "priority": 4,
                "source_layers": ["L1_quant"],
            }
        )
    # India metrics guidance
    sector = (india.get("sector") or {})
    if sector.get("flag_high_sector"):
        issues.append(
            {
                "title": "Sector concentration (India)",
                "annual_cost_rs": 0,
                "severity": "medium",
                "description": (
                    f"Top sector weight ~{sector.get('top_sector_pct')}% "
                    f"(L1 India metric)."
                ),
                "fix": "Diversify across sectors (IT/Financials often dominate Indian books).",
                "priority": 4,
                "source_layers": ["L1_quant_india"],
            }
        )
    liq = india.get("liquidity") or {}
    if float(liq.get("score_0_100") or 100) < 40:
        issues.append(
            {
                "title": "Low liquidity / lock-ins",
                "annual_cost_rs": 0,
                "severity": "medium",
                "description": (
                    f"Liquid share ~{liq.get('liquid_pct')}% "
                    f"(ELSS/PPF/FD/NPS locks reduce flexibility)."
                ),
                "fix": "Keep emergency bucket in liquid debt/arbitrage; don't over-lock.",
                "priority": 5,
                "source_layers": ["L1_quant_india"],
            }
        )
    tax = float(india.get("est_tax_if_fully_sold_rs") or 0)
    if tax > analysis["total_value"] * 0.08:
        issues.append(
            {
                "title": "High illustrative tax drag if sold",
                "annual_cost_rs": round(tax * 0.05, 2),
                "severity": "low",
                "description": (
                    f"Est. tax if fully sold ~₹{tax:,.0f} "
                    f"(India STCG/LTCG/debt proxy — not a bill)."
                ),
                "fix": "Prefer tax-aware switches; use LTCG bands; avoid unnecessary churn.",
                "priority": 6,
                "source_layers": ["L1_quant_india"],
            }
        )
    # Trained model flags (soft, labeled)
    preds = (trained.get("predictions") or {}) if trained.get("available") else {}
    if preds.get("has_overlap", {}).get("flag") and not analysis.get("overlap_pairs"):
        issues.append(
            {
                "title": "ML flag: overlap risk pattern",
                "annual_cost_rs": 0,
                "severity": "low",
                "description": (
                    f"Trained India model P(overlap)="
                    f"{preds['has_overlap']['probability']} "
                    f"(pattern match on features; confirm with holdings)."
                ),
                "fix": "Review large-cap fund pairs even if holdings DB incomplete.",
                "priority": 5,
                "source_layers": ["L2_ml_trained"],
            }
        )
    px = analysis.get("portfolio_xirr")
    if px is not None and px < 10:
        issues.append(
            {
                "title": "Below-Benchmark Returns",
                "annual_cost_rs": round(analysis["total_value"] * 0.025, 2),
                "severity": "high" if px < 7 else "medium",
                "description": f"XIRR {px}%/yr vs Nifty 50 ref ~{BENCH['Nifty 50']}%/yr.",
                "fix": "Review lagging funds; low-cost index Direct is one option.",
                "priority": 3,
                "source_layers": ["L1_quant"],
            }
        )
    issues.sort(key=lambda x: (x.get("priority", 9), -x.get("annual_cost_rs", 0)))
    for i, iss in enumerate(issues):
        iss["rank"] = i + 1
        iss["is_free"] = i == 0
    return issues[:8]


def _score(port_xirr, total_val, ter_w, ovlp_w, risk, fraud, goal_gap, mc, trained=None):
    score = 100
    if port_xirr is not None:
        if port_xirr < 6:
            score -= 25
        elif port_xirr < 10:
            score -= 15
        elif port_xirr < 12:
            score -= 5
        if port_xirr > 15:
            score += 3
    tv = total_val or 1
    if ter_w / tv * 100 > 1.0:
        score -= 20
    elif ter_w / tv * 100 > 0.5:
        score -= 12
    elif ter_w / tv * 100 > 0.2:
        score -= 6
    if ovlp_w / tv * 100 > 0.4:
        score -= 10
    if risk.get("concentrated"):
        score -= 8
    if risk.get("risk_goal_mismatch"):
        score -= 6
    if goal_gap and goal_gap > 3:
        score -= 12
    if mc and mc.get("success_probability_pct", 100) < 40:
        score -= 8
    # Blend with trained health score if available (20% weight)
    trained = trained or {}
    if trained.get("available") and trained.get("predictions", {}).get("health_score"):
        ml_s = float(trained["predictions"]["health_score"].get("score") or score)
        score = round(0.8 * score + 0.2 * ml_s)
    score = max(15, min(98, int(score)))
    if fraud.get("critical"):
        score = min(score, 40)
    if score >= 86:
        grade, glabel = "A", "Excellent"
    elif score >= 71:
        grade, glabel = "B", "Good"
    elif score >= 56:
        grade, glabel = "C", "Fair"
    elif score >= 41:
        grade, glabel = "D", "Poor"
    else:
        grade, glabel = "F", "Critical"
    return {"score": score, "grade": grade, "grade_label": glabel}
