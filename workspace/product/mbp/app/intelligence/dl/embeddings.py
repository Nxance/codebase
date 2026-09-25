"""
L3 — representation learning interface.

Uses trained fund embedding when present; hash fallback otherwise.
Outputs feed L2/L4 — never shown as raw user returns.
"""
from __future__ import annotations

import hashlib
from typing import Iterable


def _tok_hash(token: str, dim: int) -> int:
    h = hashlib.md5(token.encode("utf-8")).hexdigest()
    return int(h, 16) % dim


class FundEmbedder:
    def __init__(self, dim: int = 32):
        self.dim = dim
        self.layer = "L3_dl"
        self.backend = "hash_embedding_v0"

    def _hash_embed(self, name: str, category: str = "") -> list[float]:
        vec = [0.0] * self.dim
        for tok in (name + " " + category).lower().split():
            if len(tok) < 2:
                continue
            i = _tok_hash(tok, self.dim)
            vec[i] += 1.0
        n = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / n for x in vec]

    def embed(self, name: str, category: str = "", extra: Iterable[str] | None = None) -> list[float]:
        try:
            from .models import embed_fund

            res = embed_fund(name, category)
            vec = list(res["vector"])
            self.backend = res.get("backend", self.backend)
            # Prefer native trained dimension (e.g. 48) over truncated hash dim
            if res.get("backend") and res.get("backend") != "hash_fallback":
                self.dim = len(vec)
                return vec
        except Exception:
            vec = self._hash_embed(name, category)
            self.backend = "hash_embedding_v0"
        if len(vec) == self.dim:
            return vec
        if len(vec) > self.dim:
            return vec[: self.dim]
        return vec + [0.0] * (self.dim - len(vec))

    def similarity(self, a: list[float], b: list[float]) -> float:
        n = min(len(a), len(b))
        if n == 0:
            return 0.0
        return sum(a[i] * b[i] for i in range(n))


_default: FundEmbedder | None = None


def _get_default() -> FundEmbedder:
    global _default
    if _default is None:
        _default = FundEmbedder()
    return _default


def embedding_similarity(name_a: str, name_b: str, cat_a: str = "", cat_b: str = "") -> float:
    from .models import similarity as trained_similarity

    return trained_similarity(name_a, name_b, cat_a, cat_b)


def diversify_by_embedding(
    candidates: list[dict], max_n: int = 6, max_pair_sim: float = 0.92
) -> list[dict]:
    """Greedy pick high FIT with embedding diversity constraint."""
    embder = _get_default()
    selected: list[dict] = []
    embeds: list[list[float]] = []
    for c in candidates:
        emb = embder.embed(c.get("name", ""), c.get("category", "") or c.get("type", ""))
        if selected:
            sims = [embder.similarity(emb, e) for e in embeds]
            if max(sims) >= max_pair_sim and len(selected) >= 2:
                continue
        selected.append({**c, "embedding_backend": embder.backend, "layer_dl": "L3_dl"})
        embeds.append(emb)
        if len(selected) >= max_n:
            break
    return selected
