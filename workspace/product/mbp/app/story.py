"""Story layer — turn engine JSON into narrative without mislabeling samples as personal loss."""
from __future__ import annotations

from typing import Any, Literal

Context = Literal["user", "sample", "empty"]


def enrich_health_story(
    report: dict[str, Any],
    *,
    context: Context = "user",
) -> dict[str, Any]:
    """
    context:
      - user: real holdings the person entered/uploaded
      - sample: canned demo portfolio — must NOT say "you're losing"
      - empty: no holdings — no loss figures at all
    """
    if context == "empty" or report.get("error"):
        report["story"] = _empty_story()
        report["analysis_context"] = "empty"
        report["is_sample"] = False
        return report

    is_sample = context == "sample" or bool(report.get("is_sample"))
    score = report.get("score") or 0
    grade = report.get("grade") or "—"
    issues = report.get("issues") or []
    ter = float(report.get("ter_waste_annual_rs") or 0)
    ovlp = float(report.get("overlap_waste_annual_rs") or 0)

    # Only count L1 economic leaks for "avoidable" hero — not soft ML scores / zero-cost flags
    avoidable = round(ter + ovlp, 0)
    if report.get("unlocked") and issues:
        economic = [
            float(i.get("annual_cost_rs") or 0)
            for i in issues
            if (i.get("source_layers") or ["L1_quant"])
            and "L1_quant" in (i.get("source_layers") or ["L1_quant"])
            and float(i.get("annual_cost_rs") or 0) > 0
        ]
        if economic:
            # Prefer sum of unique economic issue costs when unlocked; avoid double-count soft issues
            avoidable = max(avoidable, round(sum(economic), 0))

    ten_year = (
        round(avoidable * (((1.12**10) - 1) / 0.12), 0) if avoidable > 0 else 0
    )

    if score >= 80:
        verdict = "Solid foundation — only small leaks, if any."
        tone = "good"
    elif score >= 60:
        verdict = "Working, but some quantifiable inefficiencies exist."
        tone = "warn"
    elif score >= 40:
        verdict = "Needs attention — material inefficiencies detected."
        tone = "bad"
    else:
        verdict = "Critical gaps — diagnose carefully before adding capital."
        tone = "critical"

    top = issues[0] if issues else None

    if is_sample:
        if avoidable > 0:
            headline = (
                f"Example portfolio: engines quantify ~₹{int(avoidable):,}/year "
                f"in avoidable cost on this sample book."
            )
        else:
            headline = (
                "Example portfolio: no large TER/overlap leaks on this sample."
            )
        subject = "this sample"
        hero_label = "Sample avoidable cost / year"
        secondary_label = "If unfixed ~10 years (illustrative)"
    else:
        if avoidable > 0:
            headline = (
                f"On the portfolio you entered, engines quantify ~₹{int(avoidable):,}/year "
                f"in avoidable cost (TER + overlap)."
            )
        else:
            headline = (
                f"On the portfolio you entered: score {score}/100 — "
                f"no material TER/overlap leak quantified."
            )
        subject = "your entered portfolio"
        hero_label = "Avoidable cost / year (your data)"
        secondary_label = "If unfixed ~10 years (illustrative model)"

    story = {
        "headline": headline,
        "verdict": verdict,
        "tone": tone,
        "is_sample": is_sample,
        "subject": subject,
        "hero_metric": {
            "label": hero_label,
            "value_rs": avoidable if avoidable > 0 else 0,
            "display": f"₹{int(avoidable):,}" if avoidable > 0 else "₹0",
            "empty_meaning": (
                "₹0 means no Regular-vs-Direct TER leak or holdings overlap "
                "was quantified — not that markets can't go down."
            ),
        },
        "secondary_metric": {
            "label": secondary_label,
            "value_rs": ten_year,
            "display": f"₹{int(ten_year):,}" if ten_year > 0 else "—",
        },
        "score_line": f"{score}/100 · Grade {grade}",
        "top_issue_title": top.get("title") if top else None,
        "next_step": (
            top.get("fix")
            if top
            else "No ranked economic fix required from TER/overlap checks."
        ),
        "trust": [
            "Loss figures only appear when holdings exist and L1 finds TER/overlap leaks",
            "Sample demos are labelled — never treated as your money",
            "Suggestion only — you execute on your broker",
        ],
        "banner": (
            {
                "level": "sample",
                "title": "Illustrative sample — not your portfolio",
                "body": (
                    "No file was uploaded. These numbers come from a built-in example "
                    "(Regular-plan large-caps designed to show TER + overlap). "
                    "Upload or enter your holdings for a personal diagnosis."
                ),
            }
            if is_sample
            else {
                "level": "user",
                "title": "Based on holdings you provided",
                "body": (
                    "Avoidable cost = Regular vs Direct TER waste + fund-holdings overlap estimate. "
                    "It is not market loss, and not a prediction of future returns."
                ),
            }
        ),
        "payback_days": (
            max(1, int(round(99 / (avoidable / 365))))
            if (not is_sample and avoidable >= 99)
            else None
        ),
        "methodology": {
            "included_in_avoidable": ["regular_vs_direct_ter", "jaccard_overlap_proxy"],
            "excluded": [
                "market_drawdowns",
                "unrealised_pnl_as_loss",
                "ml_soft_scores",
                "benchmark_underperformance_as_cash_loss",
            ],
        },
    }
    report["story"] = story
    report["analysis_context"] = "sample" if is_sample else "user"
    report["is_sample"] = is_sample
    return report


def _empty_story() -> dict[str, Any]:
    return {
        "headline": "No portfolio loaded — nothing to diagnose yet.",
        "verdict": "Add holdings to measure returns, costs, and overlap.",
        "tone": "good",
        "is_sample": False,
        "subject": "none",
        "hero_metric": {
            "label": "Avoidable cost / year",
            "value_rs": 0,
            "display": "—",
            "empty_meaning": "No data → no loss figure. We never invent personal losses.",
        },
        "secondary_metric": {
            "label": "10-yr projection",
            "value_rs": 0,
            "display": "—",
        },
        "score_line": "—",
        "top_issue_title": None,
        "next_step": "Enter holdings, upload CSV, or run the labelled sample demo.",
        "trust": [
            "Empty state never shows a personal loss",
            "Sample demo is optional and clearly marked",
        ],
        "banner": {
            "level": "empty",
            "title": "Waiting for holdings",
            "body": "Nxance only reports avoidable cost after you provide a portfolio (or explicitly run the sample).",
        },
        "payback_days": None,
        "methodology": {
            "included_in_avoidable": [],
            "excluded": ["everything_until_data_exists"],
        },
    }


def enrich_construction_story(report: dict[str, Any]) -> dict[str, Any]:
    a = (report.get("allocation") or {}).get("allocation_pct") or {}
    er = report.get("expected_return_pct")
    p = report.get("profile") or {}
    proj = report.get("projection") or {}
    report["story"] = {
        "headline": (
            f"Proposed mix for your answers: {int(a.get('equity', 0))}% equity · "
            f"{int(a.get('debt_mf', 0))}% debt · {int(a.get('fd', 0))}% FD "
            f"({p.get('goal', 'goal')})."
        ),
        "verdict": (
            f"Model expected return ~{er}%/yr from the optimiser — suggestion only, not a guarantee."
        ),
        "tone": "good" if report.get("diversification", {}).get("ok") else "warn",
        "is_sample": False,
        "hero_metric": {
            "label": "Model expected return",
            "display": f"{er}%/yr",
        },
        "secondary_metric": {
            "label": "Projection range (illustrative)",
            "display": (
                f"₹{int(proj.get('conservative_rs') or 0):,} – "
                f"₹{int(proj.get('base_rs') or 0):,}"
                if proj
                else "—"
            ),
        },
        "banner": {
            "level": "user",
            "title": "Construction from your questionnaire",
            "body": "No market ‘loss’ is implied — this is a forward plan, not a diagnosis of past drag.",
        },
        "trust": [
            "No auto-execution",
            "Fraud gate on candidates",
            "FIT from L2 scorer + L4 weights",
        ],
    }
    report["analysis_context"] = "user"
    report["is_sample"] = False
    return report
