"""L3 deep-style models — lazy exports (avoid circular imports)."""

__all__ = [
    "FundEmbedder",
    "embedding_similarity",
    "diversify_by_embedding",
    "embed_fund",
    "similarity",
    "predict_sequence",
    "portfolio_embedding_overlap",
    "deep_status",
    "style_vector",
    "style_similarity",
    "blended_similarity",
]


def __getattr__(name: str):
    if name in ("FundEmbedder", "embedding_similarity", "diversify_by_embedding"):
        from . import embeddings as emb

        return getattr(emb, name)
    if name in (
        "embed_fund",
        "similarity",
        "predict_sequence",
        "portfolio_embedding_overlap",
        "deep_status",
    ):
        from . import models as m

        return getattr(m, name)
    if name in ("style_vector", "style_similarity", "blended_similarity"):
        from . import style_factors as sf

        return getattr(sf, name)
    raise AttributeError(name)
