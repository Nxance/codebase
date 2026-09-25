"""Number Guard — discard / rewrite AI text if numbers aren't engine-sourced."""
from __future__ import annotations

import re
from typing import Any

from .common import extract_numbers, flatten_numbers


def allowed_number_set(engine_payload: dict[str, Any]) -> set[str]:
    nums = flatten_numbers(engine_payload)
    # Always allow years, common small integers used in templates
    for i in range(0, 101):
        nums.add(str(i))
    return nums


def number_guard(text: str, engine_payload: dict[str, Any]) -> dict:
    """
    Returns {ok, text, stripped_or_original, violations}.
    If violations found → replace with safe template from engine numbers only.
    """
    allowed = allowed_number_set(engine_payload)
    found = extract_numbers(text)
    violations = []
    for n in found:
        cleaned = n.replace(",", "")
        # allow if exact or integer form matches
        if n in allowed or cleaned in allowed:
            continue
        # allow if float close match exists
        try:
            f = float(cleaned)
            if any(
                abs(float(a.replace(",", "")) - f) < 0.05
                for a in allowed
                if re.match(r"^-?\d", a.replace(",", ""))
            ):
                continue
        except Exception:
            pass
        violations.append(n)

    if not violations:
        return {"ok": True, "text": text, "violations": []}

    # Safe fallback using only engine fields
    safe = _safe_fallback(engine_payload)
    return {
        "ok": False,
        "text": safe,
        "violations": violations,
        "original_discarded": True,
    }


def _safe_fallback(payload: dict) -> str:
    score = payload.get("score")
    grade = payload.get("grade", "")
    top = None
    issues = payload.get("issues") or []
    if issues:
        top = issues[0]
    if score is not None and top:
        return (
            f"Portfolio score {score}/100 (Grade {grade}). "
            f"Top issue: {top.get('title', 'Issue')} — "
            f"about Rs {top.get('annual_cost_rs', 0)}/year. "
            f"Suggestion only — verify before acting. SEBI: this is not investment advice."
        )
    if payload.get("instruments"):
        n = len(payload["instruments"])
        er = payload.get("expected_return_pct", "—")
        return (
            f"Proposed portfolio has {n} instruments with expected return about {er}%/year. "
            f"Suggestion only — execute via your own broker if you choose."
        )
    summary = payload.get("summary") or payload.get("teaser_summary")
    if summary:
        # strip unknown numbers by keeping only digits that pass — use summary as-is if short
        return str(summary)[:500]
    return "Analysis complete. Open the full report for verified numbers from the engines."
