"""
Image preprocessing for OCR — multi-variant, Pillow if present.

Zero-cost stack: pure Pillow ops (or raw passthrough).
"""
from __future__ import annotations

import io
from typing import Any


def _has_pil() -> bool:
    try:
        from PIL import Image  # noqa: F401

        return True
    except Exception:
        return False


def load_image(data: bytes):
    from PIL import Image

    return Image.open(io.BytesIO(data)).convert("RGB")


def image_to_png_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _upscale(g, scale_min_width: int = 1400):
    from PIL import Image

    w, h = g.size
    if w < scale_min_width:
        factor = scale_min_width / max(w, 1)
        g = g.resize((int(w * factor), int(h * factor)), Image.Resampling.LANCZOS)
    return g


def preprocess_variant(img, variant: str = "default"):
    """Return grayscale-ish image ready for Tesseract."""
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps

    g = ImageOps.grayscale(img)
    g = _upscale(g, 1400 if variant != "light" else 1100)

    if variant == "light":
        g = ImageEnhance.Contrast(g).enhance(1.3)
        g = ImageEnhance.Sharpness(g).enhance(1.2)
        return g

    if variant == "binary":
        g = ImageOps.autocontrast(g, cutoff=2)
        g = ImageEnhance.Contrast(g).enhance(2.0)
        g = g.point(lambda x: 255 if x > 140 else 0)
        return g

    if variant == "soft":
        g = ImageEnhance.Contrast(g).enhance(1.4)
        g = ImageFilter.MedianFilter(size=3)
        g = ImageOps.autocontrast(g, cutoff=1)
        return g

    # default — strong but not crushed
    g = ImageEnhance.Contrast(g).enhance(1.55)
    g = ImageEnhance.Sharpness(g).enhance(1.5)
    g = g.filter(ImageFilter.MedianFilter(size=3))
    g = ImageOps.autocontrast(g, cutoff=1)
    # soft threshold (keep gray midtones for anti-aliased fonts)
    g = g.point(lambda x: 255 if x > 175 else (0 if x < 85 else int(x * 1.05)))
    return g


def preprocess_for_ocr(img, *, scale_min_width: int = 1400):
    return preprocess_variant(img, "default")


def preprocess_bytes(data: bytes) -> tuple[bytes, dict[str, Any]]:
    """Return (png_bytes, meta). Falls back to raw bytes without PIL."""
    if not _has_pil():
        return data, {"preprocessed": False, "backend": "raw_passthrough", "variant": "none"}
    try:
        img = load_image(data)
        proc = preprocess_variant(img, "default")
        return image_to_png_bytes(proc), {
            "preprocessed": True,
            "backend": "pillow",
            "variant": "default",
        }
    except Exception as e:
        return data, {"preprocessed": False, "backend": f"error:{e}", "variant": "none"}


def preprocess_variants(data: bytes) -> list[tuple[bytes, dict[str, Any]]]:
    """Multiple preprocess paths for multi-pass OCR voting."""
    if not _has_pil():
        return [(data, {"preprocessed": False, "backend": "raw", "variant": "raw"})]
    try:
        img = load_image(data)
        out = []
        for v in ("default", "soft", "binary", "light"):
            try:
                proc = preprocess_variant(img, v)
                out.append(
                    (
                        image_to_png_bytes(proc),
                        {"preprocessed": True, "backend": "pillow", "variant": v},
                    )
                )
            except Exception:
                continue
        if not out:
            out.append((data, {"preprocessed": False, "backend": "raw", "variant": "raw"}))
        return out
    except Exception as e:
        return [(data, {"preprocessed": False, "backend": f"error:{e}", "variant": "raw"})]
