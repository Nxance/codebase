"""
Nxance zero-cost OCR engine v4.

Stack: multi-variant Pillow preprocess → multi-PSM Tesseract → layout v4
       → AMFI/popular lexicon name correction.
No paid APIs. System Tesseract only.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .layout import parse_holdings_from_ocr_text
from .preprocess import preprocess_bytes, preprocess_variants


# PSM modes that work well for portfolio screenshots
PSM_MODES = (6, 4, 11, 3)


def ocr_available() -> dict[str, Any]:
    tess = shutil.which("tesseract")
    try:
        import pytesseract  # noqa: F401

        py = True
    except Exception:
        py = False
    try:
        from PIL import Image  # noqa: F401

        pil = True
    except Exception:
        pil = False
    return {
        "tesseract_bin": bool(tess),
        "tesseract_path": tess,
        "pytesseract": py,
        "pillow": pil,
        "ready": bool(tess),
        "engine": "nxance_ocr_v4",
        "cost": "zero",
        "note": "brew install tesseract; optional: pip install pillow pytesseract",
        "features": [
            "multi_psm",
            "multi_preprocess",
            "layout_v4",
            "lexicon_correct",
            "confidence_pick",
        ],
    }


def _tesseract_cli(png_bytes: bytes, *, psm: int = 6, timeout: int = 45) -> str:
    tess = shutil.which("tesseract")
    if not tess:
        raise RuntimeError("tesseract not installed (brew install tesseract)")
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(png_bytes)
        path = f.name
    try:
        out = subprocess.check_output(
            [tess, path, "stdout", "--psm", str(psm), "-l", "eng"],
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        return out.decode("utf-8", errors="ignore")
    finally:
        Path(path).unlink(missing_ok=True)


def _score_parse(portfolio: dict[str, Any], text: str) -> float:
    lots = portfolio.get("lots") or []
    conf = float((portfolio.get("source") or {}).get("parse_confidence") or 0)
    n = len(lots)
    # Prefer more holdings with sane values + text evidence
    value = sum(float(l.get("current_value") or 0) for l in lots)
    text_len = min(len(text), 4000) / 4000
    return n * 2.0 + conf * 3.0 + min(value / 1e6, 2.0) + text_len


def _ocr_once(png_bytes: bytes, *, psm: int, use_py: bool) -> str:
    if use_py:
        try:
            from PIL import Image
            import io
            import pytesseract

            img = Image.open(io.BytesIO(png_bytes))
            return pytesseract.image_to_string(img, config=f"--psm {psm}")
        except Exception:
            pass
    return _tesseract_cli(png_bytes, psm=psm)


def ocr_image_bytes(data: bytes, *, max_passes: int = 6) -> dict[str, Any]:
    """
    Multi-pass OCR. Picks the parse with best score.
    max_passes keeps latency reasonable on mobile screenshots.
    """
    status = ocr_available()
    if not status["ready"]:
        png, meta = preprocess_bytes(data)
        empty = parse_holdings_from_ocr_text("")
        empty["source"]["ocr_backend"] = "tesseract_missing"
        empty["source"]["preprocessed"] = meta.get("preprocessed", False)
        empty["source"]["tesseract_ready"] = False
        empty["ocr_text"] = ""
        empty["ocr_status"] = status
        return empty

    use_py = bool(status.get("pytesseract") and status.get("pillow"))
    variants = preprocess_variants(data) if status.get("pillow") else [
        (data, {"preprocessed": False, "backend": "raw", "variant": "raw"})
    ]

    best_port: dict[str, Any] | None = None
    best_score = -1.0
    best_text = ""
    best_backend = "none"
    passes = 0

    # Fast path first: default preprocess + PSM 6
    for png, meta in variants[:2]:
        for psm in (6, 4):
            if passes >= max_passes:
                break
            try:
                text = _ocr_once(png, psm=psm, use_py=use_py)
            except Exception as e:
                text = ""
                backend = f"error:{e}"
            else:
                backend = f"{'pytesseract' if use_py else 'cli'}+{meta.get('variant','raw')}+psm{psm}"
            passes += 1
            if not text.strip():
                continue
            port = parse_holdings_from_ocr_text(text)
            sc = _score_parse(port, text)
            if sc > best_score:
                best_score = sc
                best_port = port
                best_text = text
                best_backend = backend
        if passes >= max_passes:
            break

    # If weak result, try remaining variants/PSMs
    if best_score < 4.0 and passes < max_passes:
        for png, meta in variants:
            for psm in PSM_MODES:
                if passes >= max_passes:
                    break
                key = f"{meta.get('variant')}-{psm}"
                if key in (best_backend,):
                    continue
                try:
                    text = _ocr_once(png, psm=psm, use_py=use_py)
                except Exception:
                    passes += 1
                    continue
                passes += 1
                if not text.strip():
                    continue
                port = parse_holdings_from_ocr_text(text)
                sc = _score_parse(port, text)
                if sc > best_score:
                    best_score = sc
                    best_port = port
                    best_text = text
                    best_backend = (
                        f"{'pytesseract' if use_py else 'cli'}+{meta.get('variant','raw')}+psm{psm}"
                    )

    if best_port is None:
        best_port = {
            "schema_version": "india_portfolio_v1",
            "source": {
                "channel": "ocr_screenshot",
                "parse_confidence": 0.0,
                "engine": "empty",
            },
            "lots": [],
            "as_of": __import__("datetime").date.today().isoformat(),
            "currency": "INR",
            "holder": {},
            "cashflows": [],
            "meta": {},
        }

    best_port["source"]["ocr_backend"] = best_backend
    best_port["source"]["preprocessed"] = True
    best_port["source"]["tesseract_ready"] = True
    best_port["source"]["ocr_passes"] = passes
    best_port["source"]["ocr_score"] = round(best_score, 3)
    best_port["ocr_text"] = best_text[:8000]
    best_port["ocr_status"] = status
    return best_port


def ocr_image_path(path: str) -> dict[str, Any]:
    return ocr_image_bytes(Path(path).read_bytes())


def extract_portfolio_from_image(data: bytes) -> dict[str, Any]:
    return ocr_image_bytes(data)
