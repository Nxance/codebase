"""
Synthetic portfolio 'screenshots' for OCR eval.

Prefer Pillow; else ImageMagick `convert` (free, already on this Mac).
"""
from __future__ import annotations

import random
import subprocess
import tempfile
from pathlib import Path
from typing import Any

RNG = random.Random(21)


def random_holdings(n: int = 4) -> list[dict]:
    names = [
        "Axis Bluechip Regular",
        "HDFC Flexi Cap Direct",
        "UTI Nifty 50 Index Direct",
        "Parag Parikh Flexi Cap Direct",
        "SBI Small Cap Regular",
        "Mirae Asset Large Cap Regular",
        "ICICI Pru Bluechip Direct",
        "Reliance Industries",
        "HDFC Bank",
        "SBI FD 3yr",
    ]
    RNG.shuffle(names)
    lots = []
    for name in names[:n]:
        inv = RNG.uniform(20000, 200000)
        cur = inv * RNG.uniform(0.9, 1.6)
        plan = "direct" if "Direct" in name else "regular" if "Regular" in name else "na"
        ac = "fd" if "FD" in name else "stock" if name in ("Reliance Industries", "HDFC Bank") else "mutual_fund"
        lots.append(
            {
                "name": name,
                "invested_amount": round(inv, 2),
                "current_value": round(cur, 2),
                "plan_type": plan if ac == "mutual_fund" else "regular",
                "asset_class": "mutual_fund" if ac == "mutual_fund" else ac,
            }
        )
    return lots


def _text_for_holdings(holdings: list[dict], title: str) -> str:
    """
    Ground-truth plain text matching common mobile card layout:
      Fund Name
      DIRECT  Rs 50,000 -> Rs 60,000
    Also includes a single-line Groww-style variant mixed in for robustness tests.
    """
    lines = [title, "Holdings"]
    for i, lot in enumerate(holdings):
        name = str(lot.get("name", "Fund"))
        cur = float(lot.get("current_value") or 0)
        inv = float(lot.get("invested_amount") or cur)
        plan = lot.get("plan_type") or "regular"
        if i % 2 == 0:
            # two-line card (matches rendered image)
            lines.append(name)
            lines.append(f"{str(plan).upper()}  Rs {inv:,.0f} -> Rs {cur:,.0f}")
        else:
            # single-line compact
            lines.append(
                f"{name}  {plan}  Invested Rs {inv:,.0f}  Current Rs {cur:,.0f}"
            )
    return "\n".join(lines)


def render_portfolio_image(holdings: list[dict], *, title: str = "My Investments") -> tuple[bytes, str]:
    plain = _text_for_holdings(holdings, title)
    # Try Pillow
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        w, row_h = 900, 48
        h = 120 + row_h * (len(holdings) + 2)
        img = Image.new("RGB", (w, h), (10, 22, 40))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 20)
            font_sm = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
            font_b = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 24)
        except Exception:
            font = font_sm = font_b = ImageFont.load_default()
        draw.rectangle([0, 0, w, 64], fill=(15, 39, 68))
        draw.text((24, 18), title, fill=(61, 220, 255), font=font_b)
        draw.text((24, 72), "Holdings", fill=(155, 180, 204), font=font_sm)
        y = 100
        for lot in holdings:
            name = str(lot.get("name", "Fund"))[:42]
            cur = float(lot.get("current_value") or 0)
            inv = float(lot.get("invested_amount") or cur)
            plan = lot.get("plan_type") or "regular"
            draw.text((24, y), name, fill=(244, 248, 252), font=font)
            draw.text((24, y + 22), f"{plan.upper()}  Rs {inv:,.0f} -> Rs {cur:,.0f}", fill=(155, 180, 204), font=font_sm)
            y += row_h
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue(), plain
    except Exception:
        pass

    # ImageMagick convert (free, available on this Mac)
    convert = Path("/opt/homebrew/bin/convert")
    if convert.exists():
        with tempfile.TemporaryDirectory() as td:
            txt = Path(td) / "p.txt"
            png = Path(td) / "p.png"
            txt.write_text(plain)
            subprocess.check_call(
                [
                    str(convert),
                    "-size",
                    "900x600",
                    "xc:#0A1628",
                    "-fill",
                    "#F4F8FC",
                    "-pointsize",
                    "18",
                    "-gravity",
                    "NorthWest",
                    "-annotate",
                    "+20+20",
                    f"@{txt}",
                    str(png),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return png.read_bytes(), plain

    # Last resort: empty 1x1 png header + plain text for layout-only tests
    # Minimal valid PNG
    import struct
    import zlib

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\xff" * 3 for _ in range(8))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return png, plain
