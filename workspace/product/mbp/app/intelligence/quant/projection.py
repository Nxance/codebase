"""L1 — projections & simple Monte Carlo (deterministic RNG seed for reproducibility)."""
from __future__ import annotations

import math
import random
from typing import Optional


def projection_range(
    lumpsum: float,
    monthly_sip: float,
    years: float,
    expected_return_pct: float,
    shock_pct: float = 3.0,
) -> dict:
    """Closed-form FV at base and base−shock. Not a guarantee."""

    def fv(r_pct: float) -> float:
        r = r_pct / 100
        rm = r / 12
        n = years * 12
        if abs(rm) < 1e-12:
            sip_fv = monthly_sip * n
        else:
            sip_fv = monthly_sip * (((1 + rm) ** n - 1) / rm) if monthly_sip else 0
        lump_fv = lumpsum * ((1 + r) ** years) if lumpsum else 0
        return round(sip_fv + lump_fv, 0)

    base = fv(expected_return_pct)
    low = fv(max(expected_return_pct - shock_pct, 1.0))
    return {
        "base_rs": base,
        "conservative_rs": low,
        "years": years,
        "method": "closed_form_fv",
        "layer": "L1_quant",
        "note": "Range uses model returns; not a guarantee.",
    }


def monte_carlo_goal_probability(
    current_value: float,
    monthly_sip: float,
    years: float,
    target: float,
    mu_pct: float,
    sigma_pct: float = 14.0,
    paths: int = 2000,
    seed: int = 42,
) -> Optional[dict]:
    """
    Geometric Brownian-style annual steps (simplified monthly).
    Returns estimated P(wealth >= target). L1 simulation, not ML.
    """
    if years <= 0 or target <= 0:
        return None
    rng = random.Random(seed)
    mu = mu_pct / 100
    sigma = sigma_pct / 100
    n = max(1, int(years * 12))
    dt = 1 / 12
    hits = 0
    finals = []
    for _ in range(paths):
        w = current_value
        for _m in range(n):
            z = rng.gauss(0, 1)
            # monthly log-return approx
            r = (mu - 0.5 * sigma * sigma) * dt + sigma * math.sqrt(dt) * z
            w = w * math.exp(r) + monthly_sip
        finals.append(w)
        if w >= target:
            hits += 1
    finals.sort()
    p10 = finals[int(0.10 * paths)]
    p50 = finals[int(0.50 * paths)]
    p90 = finals[int(0.90 * paths)]
    return {
        "success_probability_pct": round(100 * hits / paths, 1),
        "p10_rs": round(p10, 0),
        "p50_rs": round(p50, 0),
        "p90_rs": round(p90, 0),
        "paths": paths,
        "mu_pct": mu_pct,
        "sigma_pct": sigma_pct,
        "method": "gbm_monte_carlo",
        "layer": "L1_quant",
    }
