"""L2 — soft anomaly detection (z-score / isolation-style rules)."""
from __future__ import annotations

from typing import Any


def anomaly_flags(holdings: list[dict]) -> list[dict[str, Any]]:
    """
    Soft signals (do not hard-fail like fraud gate).
    Real IsolationForest can replace internals later.
    """
    flags = []
    xirrs = [h["xirr"] for h in holdings if h.get("xirr") is not None]
    if len(xirrs) >= 2:
        mean = sum(xirrs) / len(xirrs)
        var = sum((x - mean) ** 2 for x in xirrs) / len(xirrs)
        std = var ** 0.5 or 1.0
        for h in holdings:
            if h.get("xirr") is None:
                continue
            z = (h["xirr"] - mean) / std
            if abs(z) >= 2.0:
                flags.append(
                    {
                        "name": h["name"],
                        "type": "xirr_outlier",
                        "z_score": round(z, 2),
                        "severity": "medium",
                        "message": f"{h['name']} XIRR is an outlier vs rest of portfolio (z={z:.1f}).",
                        "layer": "L2_ml",
                    }
                )
    for h in holdings:
        if h.get("asset_class") == "mutual_fund" and float(h.get("ter") or 0) >= 1.8:
            flags.append(
                {
                    "name": h["name"],
                    "type": "high_ter",
                    "severity": "low",
                    "message": f"{h['name']} TER {h.get('ter')}% is high vs typical Direct plans.",
                    "layer": "L2_ml",
                }
            )
    return flags
