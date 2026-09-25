"""L5 safety — Number Guard."""
from __future__ import annotations

import re
from typing import Any


def extract_numbers(text: str) -> set[str]:
    found = set(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text.replace("₹", "")))
    for n in re.findall(r"\d+\.?\d*", text):
        found.add(n)
    return found


def flatten_numbers(obj: Any, out: set | None = None) -> set[str]:
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


def number_guard(text: str, engine_payload: dict) -> dict:
    allowed = flatten_numbers(engine_payload)
    for i in range(0, 101):
        allowed.add(str(i))
    found = extract_numbers(text)
    violations = []
    for n in found:
        cleaned = n.replace(",", "")
        if n in allowed or cleaned in allowed:
            continue
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
        return {"ok": True, "text": text, "violations": [], "layer": "L5_nlp"}
    # Safe fallback
    score = engine_payload.get("score")
    issues = engine_payload.get("issues") or []
    top = issues[0] if issues else None
    if score is not None and top:
        safe = (
            f"Portfolio score {score}/100. Top issue: {top.get('title')} — "
            f"about Rs {top.get('annual_cost_rs', 0)}/year. Suggestion only."
        )
    else:
        safe = str(engine_payload.get("teaser_summary") or engine_payload.get("summary") or "Analysis complete.")[:500]
    return {
        "ok": False,
        "text": safe,
        "violations": violations,
        "original_discarded": True,
        "layer": "L5_nlp",
    }
