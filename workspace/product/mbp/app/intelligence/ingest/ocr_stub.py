"""
OCR path stub for screenshots (Groww/Zerodha/Bank FD).

Production: Tesseract / cloud OCR → same regex/table extraction as CAS.
Always outputs india_portfolio_v1 for training parity.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from .cas_stub import parse_cas_text


def parse_ocr_text(text: str, channel: str = "ocr_screenshot") -> dict[str, Any]:
    doc = parse_cas_text(text, channel=channel)
    doc["source"]["format"] = "image_png"
    doc["source"]["channel"] = channel
    doc["source"]["notes"] = (
        "OCR text path. Image→text is external; we only require text that maps to india_portfolio_v1."
    )
    doc["as_of"] = date.today().isoformat()
    return doc
