"""Zero-cost OCR engine — Tesseract when available, layout fallbacks always.

Lazy imports so layout-only use never pulls Pillow/Tesseract.
"""

__all__ = [
    "ocr_image_bytes",
    "ocr_image_path",
    "ocr_available",
    "extract_portfolio_from_image",
    "parse_holdings_from_ocr_text",
]


def __getattr__(name: str):
    if name == "parse_holdings_from_ocr_text":
        from .layout import parse_holdings_from_ocr_text

        return parse_holdings_from_ocr_text
    if name in (
        "ocr_image_bytes",
        "ocr_image_path",
        "ocr_available",
        "extract_portfolio_from_image",
    ):
        from . import engine

        return getattr(engine, name)
    raise AttributeError(name)
