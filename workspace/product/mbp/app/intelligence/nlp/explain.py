"""L5 — explanation templates (LLM slot later)."""
from __future__ import annotations

from typing import Any, Optional

from .guard import number_guard
from .intent import route_intent


def explain_payload(report: dict[str, Any]) -> dict:
    engine = report.get("engine")
    if engine == "health_check":
        text = _hc(report)
    elif engine == "construction":
        text = _con(report)
    else:
        text = report.get("teaser_summary") or report.get("summary") or "No report."
    g = number_guard(text, report)
    return {
        "mode": "explain",
        "text": g["text"],
        "number_guard_ok": g["ok"],
        "violations": g.get("violations") or [],
        "layer": "L5_nlp",
        "stack_note": report.get("intelligence_stack"),
    }


def _hc(r: dict) -> str:
    parts = [
        f"Your portfolio health score is {r.get('score')}/100 (Grade {r.get('grade')}).",
        f"Portfolio value is about Rs {r.get('total_value')}.",
    ]
    if r.get("portfolio_xirr") is not None:
        parts.append(f"XIRR is about {r['portfolio_xirr']}% per year.")
    issues = r.get("issues") or []
    if issues:
        top = issues[0]
        parts.append(
            f"Biggest issue: {top.get('title')} — roughly Rs {top.get('annual_cost_rs', 0)} per year."
        )
        if top.get("fix"):
            parts.append(f"Suggested fix: {top['fix']}")
    # Mention stack honestly
    stack = r.get("intelligence_stack") or {}
    if stack:
        parts.append(
            "Numbers come from quant engines; quality scores from the ML layer; language only explains."
        )
    if not r.get("unlocked"):
        parts.append("Unlock the full report for all ranked fixes.")
    parts.append("Suggestion only — not investment advice.")
    return " ".join(str(p) for p in parts)


def _con(r: dict) -> str:
    p = r.get("profile") or {}
    a = (r.get("allocation") or {}).get("allocation_pct") or {}
    er = r.get("expected_return_pct")
    parts = [
        f"For goal {p.get('goal')} over {p.get('years')} years,",
        f"suggested mix is equity {a.get('equity')}%, debt MF {a.get('debt_mf')}%, FD {a.get('fd')}%.",
        f"Model expected return about {er}% per year from the optimiser layer.",
    ]
    proj = r.get("projection") or {}
    if proj.get("base_rs"):
        parts.append(
            f"Projection range roughly Rs {proj.get('conservative_rs')} to Rs {proj.get('base_rs')}."
        )
    parts.append("Suggestion only — execute via your own broker if you choose.")
    return " ".join(str(p) for p in parts)


def chat_on_payload(message: str, report: Optional[dict] = None) -> dict:
    route = route_intent(message)
    if route == "redirect_construction":
        return {
            "mode": "redirect",
            "route": "construction",
            "text": "Use Construction — the optimiser designs the plan; chat does not invent portfolios.",
            "number_guard_ok": True,
            "layer": "L5_nlp",
        }
    if route == "redirect_health_check":
        return {
            "mode": "redirect",
            "route": "health_check",
            "text": "Use Health Check to upload holdings. I only explain verified engine numbers.",
            "number_guard_ok": True,
            "layer": "L5_nlp",
        }
    if route == "refuse_execution":
        return {
            "mode": "refuse",
            "text": "Nxance is suggestion-only. No buy/sell orders from chat.",
            "number_guard_ok": True,
            "layer": "L5_nlp",
        }
    if not report:
        return {
            "mode": "chat",
            "text": "Run Health Check or Construction first. Language layer needs a verified payload.",
            "number_guard_ok": True,
            "layer": "L5_nlp",
        }
    m = message.lower()
    if "xirr" in m and report.get("portfolio_xirr") is not None:
        text = f"Your portfolio XIRR from the quant layer is {report['portfolio_xirr']}% per year."
    elif "score" in m and report.get("score") is not None:
        text = f"Health score is {report['score']}/100 (Grade {report.get('grade')})."
    elif "ml" in m or "model" in m or "layer" in m:
        stack = report.get("intelligence_stack") or {}
        text = (
            f"Stack used: {stack}. "
            "L1 quant measures, L2 ML scores, L3 embeddings diversify, L4 optimises, L5 explains."
        )
    elif "ter" in m or "cost" in m:
        text = f"Estimated Regular-plan TER waste is about Rs {report.get('ter_waste_annual_rs', 0)} per year."
    else:
        return explain_payload(report)
    g = number_guard(text, report)
    return {
        "mode": "chat",
        "text": g["text"],
        "number_guard_ok": g["ok"],
        "violations": g.get("violations") or [],
        "layer": "L5_nlp",
    }
