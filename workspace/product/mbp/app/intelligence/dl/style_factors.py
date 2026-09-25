"""
L3 style factors — free India fund taxonomy from name text alone.

No paid category APIs. Complements trained embeddings for overlap detection.
"""
from __future__ import annotations

import math
import re
from typing import Any

# Ordered factor dimensions (stable indices for cosine)
FACTORS = [
    "large_cap",
    "mid_cap",
    "small_cap",
    "flexi_multi",
    "index_passive",
    "elss_tax",
    "debt_liquid",
    "hybrid",
    "international",
    "sectoral",
    "equity_stock",
    "fd_deposit",
    "direct_plan",
    "regular_plan",
]

_RULES: list[tuple[str, str]] = [
    (r"\b(fd|fixed\s*deposit|recurring)\b", "fd_deposit"),
    (r"\b(ltd|limited|bank|industries)\b(?!.*fund)", "equity_stock"),
    (r"\b(elss|tax\s*saver)\b", "elss_tax"),
    (r"\b(liquid|overnight|gilt|debt|bond|ultra\s*short|money\s*market|arbitrage)\b", "debt_liquid"),
    (r"\b(hybrid|balanced|multi\s*asset|aggressive\s*hybrid)\b", "hybrid"),
    (r"\b(nasdaq|us\s*equity|international|global|overseas|fof)\b", "international"),
    (r"\b(pharma|tech|technology|banking|psu|infra|consumption|energy|metal)\b", "sectoral"),
    (r"\b(index|nifty|sensex|etf|passive)\b", "index_passive"),
    (r"\b(small[\s-]?cap|smallcap)\b", "small_cap"),
    (r"\b(mid[\s-]?cap|midcap)\b", "mid_cap"),
    (r"\b(large[\s-]?cap|bluechip|blue\s*chip|nifty\s*50)\b", "large_cap"),
    (r"\b(flexi|multi[\s-]?cap|focused|value|contra|opportunit)\b", "flexi_multi"),
    (r"\bdirect\b", "direct_plan"),
    (r"\bregular\b", "regular_plan"),
]


def style_vector(name: str, category: str = "") -> list[float]:
    text = f"{name} {category}".lower()
    v = [0.0] * len(FACTORS)
    idx = {f: i for i, f in enumerate(FACTORS)}
    hits = 0
    for pat, fac in _RULES:
        if re.search(pat, text, re.I):
            v[idx[fac]] = 1.0
            hits += 1
    # Default equity active if fund-like with no style
    if hits == 0 and re.search(r"fund|equity|cap", text):
        v[idx["flexi_multi"]] = 0.6
        v[idx["large_cap"]] = 0.4
    # L2 normalize
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def style_similarity(name_a: str, name_b: str, cat_a: str = "", cat_b: str = "") -> float:
    a = style_vector(name_a, cat_a)
    b = style_vector(name_b, cat_b)
    return round(sum(x * y for x, y in zip(a, b)), 4)


def style_labels(name: str, category: str = "") -> list[str]:
    v = style_vector(name, category)
    return [FACTORS[i] for i, x in enumerate(v) if x >= 0.35]


def blended_similarity(
    emb_sim: float,
    name_a: str,
    name_b: str,
    cat_a: str = "",
    cat_b: str = "",
    *,
    emb_weight: float = 0.65,
) -> dict[str, Any]:
    """
    Blend embedding cosine with style-factor cosine.
    Style weight higher when both names are short/noisy.
    """
    st = style_similarity(name_a, name_b, cat_a, cat_b)
    # short names → trust style more (OCR / ticker noise)
    short = min(len(name_a), len(name_b)) < 18
    w_emb = 0.5 if short else emb_weight
    blended = w_emb * emb_sim + (1.0 - w_emb) * st
    return {
        "embedding_sim": round(emb_sim, 4),
        "style_sim": st,
        "blended_sim": round(blended, 4),
        "labels_a": style_labels(name_a, cat_a),
        "labels_b": style_labels(name_b, cat_b),
        "emb_weight": w_emb,
    }
