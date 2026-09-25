"""Construction — thin adapter over intelligence pipeline."""
from __future__ import annotations

from typing import Any

from app.intelligence.pipeline.construction import run_construction_pipeline


def run_construction(questionnaire: dict, unlocked: bool = False) -> dict[str, Any]:
    return run_construction_pipeline(questionnaire, unlocked=unlocked)
