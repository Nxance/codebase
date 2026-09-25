"""Load and run L3 deep-style models (embedding + sequence + cluster overlap)."""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[3]
MODELS = ROOT / "training" / "models"

EMB_CANDIDATES = [
    MODELS / "fund_embedding_v3.json",
    MODELS / "fund_embedding_v2.json",
    MODELS / "fund_embedding_v1.json",
]
SEQ_CANDIDATES = [
    MODELS / "nav_sequence_v3.json",
    MODELS / "nav_sequence_v2.json",
    MODELS / "nav_sequence_v1.json",
]


@lru_cache(maxsize=1)
def load_embedding() -> Optional[dict]:
    for p in EMB_CANDIDATES:
        if p.exists():
            return json.loads(p.read_text())
    return None


@lru_cache(maxsize=1)
def load_sequence() -> Optional[dict]:
    for p in SEQ_CANDIDATES:
        if p.exists():
            return json.loads(p.read_text())
    return None


def clear_dl_cache() -> None:
    load_embedding.cache_clear()
    load_sequence.cache_clear()


def _tokenize(name: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", name.lower()) if len(t) > 1]


def _bow(name: str, category: str, vocab: int) -> list[float]:
    v = [0.0] * vocab
    tokens = _tokenize(name) + _tokenize(category)
    for t in tokens:
        v[abs(hash(t)) % vocab] += 1.0
    # bigrams (used by fund_embedding_v3)
    for a, b in zip(tokens, tokens[1:]):
        v[abs(hash(a + "_" + b)) % vocab] += 0.5
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _matvec(W, x, b):
    return [b[i] + sum(W[i][j] * x[j] for j in range(len(x))) for i in range(len(W))]


def _norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embed_fund(name: str, category: str = "") -> dict[str, Any]:
    m = load_embedding()
    if not m:
        from .embeddings import FundEmbedder

        e = FundEmbedder(dim=32)
        return {
            "vector": e.embed(name, category),
            "backend": "hash_fallback",
            "layer": "L3_dl",
        }
    x = _bow(name, category, m["vocab_size"])
    vec = _norm(_matvec(m["W"], x, m["b"]))
    return {
        "vector": vec,
        "backend": m.get("version", "embedding"),
        "layer": "L3_dl",
        "dim": m["dim"],
    }


def similarity(name_a: str, name_b: str, cat_a: str = "", cat_b: str = "") -> float:
    ea = embed_fund(name_a, cat_a)["vector"]
    eb = embed_fund(name_b, cat_b)["vector"]
    return round(sum(x * y for x, y in zip(ea, eb)), 4)


def sequence_features_from_navs(navs: list[float]) -> list[float]:
    if len(navs) < 5:
        return [0.0] * 16
    rets = []
    for i in range(1, len(navs)):
        if navs[i - 1] > 0:
            rets.append(navs[i] / navs[i - 1] - 1)
    if not rets:
        return [0.0] * 16
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    std = math.sqrt(var)
    peak = navs[0]
    mdd = 0.0
    for n in navs:
        peak = max(peak, n)
        if peak > 0:
            mdd = min(mdd, n / peak - 1)
    last = rets[-5:] if len(rets) >= 5 else rets + [0] * (5 - len(rets))
    mom_20 = navs[-1] / navs[max(0, len(navs) - 20)] - 1 if len(navs) > 20 else 0
    mom_60 = navs[-1] / navs[max(0, len(navs) - 60)] - 1 if len(navs) > 60 else 0
    return [
        mean * 252,
        std * math.sqrt(252),
        mdd,
        mom_20,
        mom_60,
        min(rets),
        max(rets),
        last[0],
        last[1],
        last[2],
        last[3],
        last[4],
        len(rets) / 252,
        1.0 if mean > 0 else 0.0,
        abs(mean) / (std + 1e-6),
        (navs[-1] / navs[0] - 1) if navs[0] else 0,
    ]


def predict_sequence(navs: list[float]) -> dict[str, Any]:
    m = load_sequence()
    feats = sequence_features_from_navs(navs)
    if not m:
        return {
            "expected_return_proxy": round(feats[0], 4),
            "risk_score": round(feats[1], 4),
            "backend": "features_only",
            "layer": "L3_dl",
        }
    # Align feature length with model in_dim
    in_dim = int(m.get("in_dim") or len(feats))
    if len(feats) < in_dim:
        feats = feats + [0.0] * (in_dim - len(feats))
    elif len(feats) > in_dim:
        feats = feats[:in_dim]

    h = [
        max(0.0, m["b1"][i] + sum(m["W1"][i][j] * feats[j] for j in range(len(feats))))
        for i in range(m["hidden"])
    ]
    out = [
        m["b2"][k] + sum(m["W2"][k][i] * h[i] for i in range(m["hidden"])) for k in range(2)
    ]
    # Guardrails: blend with classical features so model can't go absurd
    classical_ret = feats[0]
    classical_risk = max(0.0, feats[1])
    ret = 0.6 * out[0] + 0.4 * classical_ret
    risk = max(0.0, 0.6 * out[1] + 0.4 * classical_risk)
    ret = max(-0.5, min(0.5, ret))
    risk = max(0.0, min(0.8, risk))
    return {
        "expected_return_proxy": round(ret, 4),
        "risk_score": round(risk, 4),
        "backend": m.get("version", "sequence"),
        "layer": "L3_dl",
        "features_preview": {
            "ann_mean": round(feats[0], 4),
            "ann_vol": round(feats[1], 4),
            "max_drawdown": round(feats[2], 4),
        },
    }


def portfolio_embedding_overlap(
    holdings: list[dict],
    *,
    threshold: float = 0.68,
) -> dict[str, Any]:
    """
    L3: detect style-overlapping funds via embedding cosine + style factors.
    Zero-cost substitute for paid 'similar funds' APIs.
    """
    from .style_factors import blended_similarity, style_labels

    names = []
    for h in holdings:
        n = str(h.get("name") or "").strip()
        if n:
            names.append((n, str(h.get("asset_class") or h.get("category") or "")))
    emb_meta = load_embedding() or {}
    backend = emb_meta.get("version", "none")
    if len(names) < 2:
        return {
            "pairs": [],
            "n_pairs": 0,
            "max_similarity": 0.0,
            "cluster_risk": 0.0,
            "layer": "L3_dl",
            "backend": f"{backend}+style_factors",
            "method": "embedding_x_style_v4",
        }

    vecs = [embed_fund(n, c)["vector"] for n, c in names]
    pairs = []
    max_sim = 0.0
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            emb_sim = sum(a * b for a, b in zip(vecs[i], vecs[j]))
            blend = blended_similarity(
                emb_sim, names[i][0], names[j][0], names[i][1], names[j][1]
            )
            sim = blend["blended_sim"]
            max_sim = max(max_sim, sim)
            if sim >= threshold:
                pairs.append(
                    {
                        "a": names[i][0],
                        "b": names[j][0],
                        "similarity": round(sim, 4),
                        "embedding_sim": blend["embedding_sim"],
                        "style_sim": blend["style_sim"],
                        "style_a": blend["labels_a"],
                        "style_b": blend["labels_b"],
                        "severity": "high" if sim >= 0.85 else "medium",
                        "message": (
                            f"{names[i][0]} and {names[j][0]} look style-similar "
                            f"(blend cos={sim:.2f}, style={blend['style_sim']:.2f}). "
                            "Possible overlap."
                        ),
                    }
                )
    pairs.sort(key=lambda p: -p["similarity"])
    n_possible = len(names) * (len(names) - 1) / 2
    cluster_risk = len(pairs) / n_possible if n_possible else 0.0
    # Dominant style cluster in portfolio
    all_labels: dict[str, int] = {}
    for n, c in names:
        for lab in style_labels(n, c):
            all_labels[lab] = all_labels.get(lab, 0) + 1
    dominant = sorted(all_labels.items(), key=lambda x: -x[1])[:5]
    return {
        "pairs": pairs[:12],
        "n_pairs": len(pairs),
        "max_similarity": round(max_sim, 4),
        "cluster_risk": round(cluster_risk, 4),
        "style_histogram": {k: v for k, v in dominant},
        "layer": "L3_dl",
        "backend": f"{backend}+style_factors",
        "method": "embedding_x_style_v4",
        "threshold": threshold,
    }


def deep_status() -> dict:
    """Lightweight status — file presence first; load only for version fields."""
    emb_path = next((p for p in EMB_CANDIDATES if p.exists()), None)
    seq_path = next((p for p in SEQ_CANDIDATES if p.exists()), None)
    emb = load_embedding() if emb_path else None
    seq = load_sequence() if seq_path else None
    return {
        "embedding": emb is not None,
        "embedding_version": (emb or {}).get("version"),
        "embedding_dim": (emb or {}).get("dim"),
        "embedding_path": emb_path.name if emb_path else None,
        "sequence": seq is not None,
        "sequence_version": (seq or {}).get("version"),
        "sequence_hidden": (seq or {}).get("hidden"),
        "sequence_path": seq_path.name if seq_path else None,
        "features": [
            "fund_embedding",
            "nav_sequence_mlp",
            "portfolio_cluster_overlap",
            "style_factors_v4",
        ],
        "cost": "zero",
    }
