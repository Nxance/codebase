"""L4 — weight construction (mean-variance lite)."""
from __future__ import annotations


def mean_variance_lite(
    candidates: list[dict],
    class_budget_pct: dict[str, float],
) -> list[dict]:
    """
    Within each asset class, weight proportional to fit_score / risk_penalty.
    Not full Markowitz covariance — API-ready for QP later.
    """
    if not candidates:
        return []

    def cls(c: dict) -> str:
        t = c.get("type") or c.get("asset_class") or "mutual_fund"
        if t == "fd":
            return "fd"
        if t == "stock":
            return "equity"
        if c.get("category") in ("debt", "hybrid"):
            return "debt_mf"
        return "equity"

    buckets: dict[str, list] = {"equity": [], "debt_mf": [], "fd": []}
    for c in candidates:
        buckets.setdefault(cls(c), []).append(c)

    out = []
    for bucket, items in buckets.items():
        budget = class_budget_pct.get(bucket, 0)
        if not items or budget <= 0:
            continue
        scores = []
        for it in items:
            fit = float(it.get("fit_score") or 50)
            # risk penalty
            risk = (it.get("risk") or it.get("ml", {}).get("risk") or "moderate")
            pen = 1.0
            if risk == "aggressive":
                pen = 0.85
            if risk == "conservative":
                pen = 1.05
            scores.append(max(fit, 1) * pen)
        total = sum(scores) or 1
        for it, sc in zip(items, scores):
            w = budget * (sc / total)
            out.append({**it, "allocation_pct": round(w, 2), "weight_method": "mv_lite_v1"})
    # renormalise to 100
    s = sum(i["allocation_pct"] for i in out) or 1
    for i in out:
        i["allocation_pct"] = round(i["allocation_pct"] / s * 100, 1)
        i["layer"] = "L4_optimize"
    return out


def apply_caps(
    instruments: list[dict],
    *,
    max_single: float = 40.0,
    max_stock: float = 15.0,
    monthly_sip: float = 0,
    lumpsum: float = 0,
) -> list[dict]:
    adjusted = []
    for inst in instruments:
        cap = max_stock if inst.get("type") == "stock" else max_single
        adjusted.append({**inst, "allocation_pct": min(inst["allocation_pct"], cap)})
    s = sum(i["allocation_pct"] for i in adjusted) or 1
    for i in adjusted:
        i["allocation_pct"] = round(i["allocation_pct"] / s * 100, 1)
        if monthly_sip:
            i["monthly_rs"] = round(monthly_sip * i["allocation_pct"] / 100, 0)
        if lumpsum:
            i["lumpsum_rs"] = round(lumpsum * i["allocation_pct"] / 100, 0)
    return adjusted
