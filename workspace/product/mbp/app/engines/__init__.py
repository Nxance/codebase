"""Legacy engine adapters — import modules directly to avoid circular imports."""

def __getattr__(name: str):
    if name == "run_health_check":
        from .health_check import run_health_check
        return run_health_check
    if name == "run_construction":
        from .construction import run_construction
        return run_construction
    if name in ("chat", "explain_report", "number_guard"):
        from . import nxancelm
        return getattr(nxancelm, name)
    raise AttributeError(name)
