"""Shared Fraud Gate — used by Health Check and Construction."""
from __future__ import annotations

from typing import Any

from .common import LEGIT_FRAGMENTS


def run_fraud_gate(holdings: list[dict]) -> dict[str, Any]:
    """
    7 hard-style checks (MBP simplified).
    Critical flags force health score cap at 40.
    """
    flags: list[dict] = []
    critical = False

    for h in holdings:
        name = (h.get("name") or "").strip()
        nl = name.lower()
        inv = float(h.get("invested_amount") or h.get("invested") or 0)
        cv = float(h.get("current_value") or 0)
        xirr = h.get("xirr")
        asset = (h.get("asset_class") or "mutual_fund").lower()

        # 1. Empty / junk name
        if len(name) < 2:
            flags.append(
                {
                    "check": "empty_name",
                    "severity": "critical",
                    "holding": name,
                    "message": "Holding name missing or too short.",
                }
            )
            critical = True
            continue

        # 2. Known scammy keywords
        scam_words = ["guaranteed triple", "double money", "crypto pump", "whatsapp tip", "sure shot"]
        if any(w in nl for w in scam_words):
            flags.append(
                {
                    "check": "scam_language",
                    "severity": "critical",
                    "holding": name,
                    "message": f"'{name}' matches scam-language patterns. Do not treat as a real investment.",
                }
            )
            critical = True

        # 3. Impossible return
        if xirr is not None and xirr > 80:
            flags.append(
                {
                    "check": "impossible_return",
                    "severity": "critical",
                    "holding": name,
                    "message": f"XIRR {xirr}% is implausible for a liquid MF/stock/FD holding — verify data or fraud.",
                }
            )
            critical = True
        elif xirr is not None and xirr > 45:
            flags.append(
                {
                    "check": "extreme_return",
                    "severity": "high",
                    "holding": name,
                    "message": f"XIRR {xirr}% is unusually high — double-check units/NAV/dates.",
                }
            )

        # 4. Negative or zero values
        if cv < 0 or inv < 0:
            flags.append(
                {
                    "check": "negative_value",
                    "severity": "critical",
                    "holding": name,
                    "message": "Negative invested/current value is invalid.",
                }
            )
            critical = True

        # 5. Unknown product outside whitelist fragments (soft for stocks; hard for MF-like names claiming SEBI)
        if asset in ("mutual_fund", "mf") and not any(f in nl for f in LEGIT_FRAGMENTS):
            # unknown AMC-like product
            if "fund" in nl or "scheme" in nl or "plan" in nl:
                flags.append(
                    {
                        "check": "unknown_scheme",
                        "severity": "high",
                        "holding": name,
                        "message": f"'{name}' does not match known AMC/index patterns — verify SEBI/AMFI registration.",
                    }
                )

        # 6. Units vs value inconsistency if both present
        units = h.get("units")
        nav = h.get("current_nav")
        if units and nav and cv > 0:
            expected = float(units) * float(nav)
            if expected > 0 and abs(expected - cv) / expected > 0.15:
                flags.append(
                    {
                        "check": "units_value_mismatch",
                        "severity": "medium",
                        "holding": name,
                        "message": f"Units×NAV (₹{expected:,.0f}) differs from stated value (₹{cv:,.0f}) by >15%.",
                    }
                )

        # 7. FD principal sanity
        if asset in ("fd", "fixed_deposit") and inv > 0 and cv > inv * 3 and (xirr or 0) > 20:
            flags.append(
                {
                    "check": "fd_impossible",
                    "severity": "critical",
                    "holding": name,
                    "message": "FD-like holding shows growth inconsistent with regulated bank FD rates.",
                }
            )
            critical = True

    return {
        "flags": flags,
        "critical": critical,
        "flag_count": len(flags),
        "pass": not critical and not any(f["severity"] == "high" for f in flags),
        "summary": (
            "Critical fraud flags — score capped."
            if critical
            else ("Review high-severity flags." if flags else "No fraud flags.")
        ),
    }
