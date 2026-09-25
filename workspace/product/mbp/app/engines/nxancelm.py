"""NxanceLM — L5 adapter."""
from __future__ import annotations

from typing import Any, Optional

from app.intelligence.nlp.explain import chat_on_payload, explain_payload
from app.intelligence.nlp.guard import number_guard as ng
from app.intelligence.nlp.intent import route_intent


def intent_route(message: str) -> str:
    return route_intent(message)


def explain_report(report: dict[str, Any]) -> dict:
    return explain_payload(report)


def chat(message: str, report: Optional[dict] = None) -> dict:
    return chat_on_payload(message, report)


number_guard = ng
