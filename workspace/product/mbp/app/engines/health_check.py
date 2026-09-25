"""Health Check — thin adapter over intelligence pipeline."""
from __future__ import annotations

from typing import Any

from app.intelligence.pipeline.health import run_health_pipeline


def run_health_check(
    holdings_raw: list[dict],
    questionnaire: dict,
    unlocked: bool = False,
) -> dict[str, Any]:
    return run_health_pipeline(holdings_raw, questionnaire, unlocked=unlocked)
