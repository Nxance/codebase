"""
Nxance multi-layer intelligence stack.

L1 quant → L2 ml → L3 dl → L4 optimize → L5 nlp
Lazy exports — avoid circular imports on package load.
"""

__all__ = ["run_health_pipeline", "run_construction_pipeline"]


def __getattr__(name: str):
    if name == "run_health_pipeline":
        from .pipeline.health import run_health_pipeline

        return run_health_pipeline
    if name == "run_construction_pipeline":
        from .pipeline.construction import run_construction_pipeline

        return run_construction_pipeline
    raise AttributeError(name)
