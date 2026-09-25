"""
CAS text extractor stub (CDSL/NSDL/CAMS/KFin).

Production: pdfplumber/pymupdf + password PAN unlock + layout tables.
Training/prep: accepts plain-text dumps or synthetic CAS-like lines and maps to schema.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any


# Example line patterns seen in Indian CAS / MF statements
LINE_PATTERNS = [
    # NAME  ISIN  QTY  VALUE
    re.compile(
        r"(?P<name>[A-Za-z0-9 &./()-]{4,60})\s+(?P<isin>INE[A-Z0-9]{9})\s+(?P<qty>[\d,.]+)\s+(?P<value>[\d,.]+)"
    ),
    # MF: scheme units nav value
    re.compile(
        r"(?P<name>(?:Axis|HDFC|SBI|ICICI|Mirae|UTI|Parag|Kotak|Nippon|Aditya)[^\n]{5,50}?)\s+(?P<qty>[\d,.]+)\s+(?P<nav>[\d.]+)\s+(?P<value>[\d,.]+)",
        re.I,
    ),
]


def parse_cas_text(text: str, channel: str = "cas_cams") -> dict[str, Any]:
    lots = []
    for i, line in enumerate(text.splitlines()):
        line = line.strip()
        if len(line) < 10:
            continue
        for pat in LINE_PATTERNS:
            m = pat.search(line)
            if not m:
                continue
            gd = m.groupdict()
            try:
                qty = float(gd.get("qty", "1").replace(",", ""))
                value = float(gd.get("value", "0").replace(",", ""))
            except Exception:
                continue
            name = gd.get("name", "").strip()
            isin = gd.get("isin")
            asset_class = "equity_stock" if isin else "mutual_fund_equity"
            lots.append(
                {
                    "lot_id": f"cas_{i}",
                    "asset_class": asset_class,
                    "name": name,
                    "isin": isin,
                    "quantity": qty,
                    "avg_cost": 0,
                    "invested_amount": value * 0.85,  # unknown cost → proxy for training
                    "current_value": value,
                    "plan_type": "regular" if "regular" in name.lower() else "direct" if "direct" in name.lower() else "regular",
                    "purchase_date": "2022-01-01",
                    "sector": "unknown",
                    "market_cap_bucket": "multi",
                    "source_row": {"raw": line},
                }
            )
            break

    conf = 0.55 if lots else 0.1
    return {
        "schema_version": "india_portfolio_v1",
        "source": {
            "channel": channel,
            "format": "pdf_cas",
            "parse_confidence": conf,
            "notes": "Stub parser — replace with full CAS PDF pipeline; schema is stable.",
        },
        "as_of": date.today().isoformat(),
        "currency": "INR",
        "holder": {},
        "lots": lots,
        "cashflows": [],
        "meta": {"tax_residency": "IN"},
    }
