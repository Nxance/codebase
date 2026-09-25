"""L5 — intent routing only."""


def route_intent(message: str) -> str:
    m = (message or "").lower()
    if any(w in m for w in ("build", "construct", "allocate", "sip plan", "new portfolio")):
        return "redirect_construction"
    if any(w in m for w in ("analyse", "analyze", "health", "overlap", "ter", "xirr", "upload")):
        return "redirect_health_check"
    if any(w in m for w in ("why", "explain", "summary", "report", "score", "issue")):
        return "explain"
    if any(w in m for w in ("buy", "sell", "order", "execute", "invest now")):
        return "refuse_execution"
    return "chat"
