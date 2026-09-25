#!/usr/bin/env python3
"""
Build Nxance Product Demo video offline (Pillow frames + ffmpeg).
Does not need the API running — Abhiyan-style release asset.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEMO = Path(__file__).resolve().parent
FRAMES = DEMO / "frames"
PARTS = DEMO / "assemble_parts"
OUT = DEMO / "Nxance_Product_Demo.mp4"
OUT_FULL = DEMO / "Nxance_Full_Owner_Demo.mp4"
W, H = 1280, 800
NAVY = (10, 22, 40)
CARD = (21, 44, 72)
ACCENT = (61, 220, 255)
TEXT = (244, 248, 252)
MUTED = (155, 180, 204)
DANGER = (255, 107, 122)
OK = (61, 220, 151)
BORDER = (40, 70, 100)


def font(size: int, bold: bool = False):
    paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def base():
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 56], fill=(5, 11, 20))
    d.rectangle([0, 0, 10, H], fill=ACCENT)
    d.rounded_rectangle([20, 12, 52, 44], radius=8, fill=ACCENT)
    d.text((28, 16), "N", fill=NAVY, font=font(20, True))
    d.text((62, 18), "nxance", fill=TEXT, font=font(22, True))
    d.rounded_rectangle([W - 220, 14, W - 24, 42], radius=12, fill=(20, 50, 70))
    d.text((W - 205, 18), "LIVE DEMO · ₹0", fill=ACCENT, font=font(14, True))
    return img, d


def card(d, xy, wh, title, body_lines, accent_left=False):
    x, y = xy
    w, h = wh
    d.rounded_rectangle([x, y, x + w, y + h], radius=16, fill=CARD, outline=BORDER, width=1)
    if accent_left:
        d.rectangle([x, y + 8, x + 4, y + h - 8], fill=ACCENT)
    d.text((x + 18, y + 14), title, fill=TEXT, font=font(18, True))
    yy = y + 48
    for line in body_lines:
        d.text((x + 18, yy), line, fill=MUTED, font=font(15))
        yy += 24


def kpi(d, x, y, label, value, color=TEXT):
    d.rounded_rectangle([x, y, x + 180, y + 86], radius=12, fill=(8, 18, 32), outline=BORDER)
    d.text((x + 14, y + 12), label, fill=MUTED, font=font(12, True))
    d.text((x + 14, y + 38), value, fill=color, font=font(26, True))


def save(img: Image.Image, name: str):
    FRAMES.mkdir(parents=True, exist_ok=True)
    path = FRAMES / name
    img.save(path, "PNG")
    print("frame", name, flush=True)
    return path


def make_frames():
    frames = []

    # 00 title
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 12, H], fill=ACCENT)
    d.text((70, 280), "nxance", fill=TEXT, font=font(72, True))
    d.text((70, 370), "Portfolio intelligence for India", fill=MUTED, font=font(28))
    d.text((70, 430), "Working demo · real engines · ₹0 stack", fill=ACCENT, font=font(22, True))
    frames.append(save(img, "00_title.png"))

    # 01 login
    img, d = base()
    d.text((40, 80), "STEP 01 · LOGIN", fill=ACCENT, font=font(14, True))
    d.text((40, 110), "Demo auth in under a second", fill=TEXT, font=font(36, True))
    d.text((40, 160), "Name + phone session — no OTP cost. Guest path always works.", fill=MUTED, font=font(18))
    card(d, (40, 220), (560, 220), "Signed in", [
        "Demo Investor",
        "Phone 9876500001",
        "token set · unlocked: false",
        "",
        "₹0 auth stack — no SMS gateway",
    ], True)
    card(d, (640, 220), (560, 220), "Session ready", [
        "Feeds Health · Upload · Pay",
        "Same session on Android APK",
        "Codes: DEMO-UNLOCK",
        "",
        "Suggestion only · not SEBI advice",
    ])
    frames.append(save(img, "01_login.png"))

    # 02 sample health
    img, d = base()
    d.text((40, 80), "STEP 02 · SAMPLE HEALTH", fill=ACCENT, font=font(14, True))
    d.text((40, 110), "One click on a labelled sample", fill=TEXT, font=font(34, True))
    d.rounded_rectangle([40, 160, 420, 190], radius=10, fill=(60, 40, 20))
    d.text((55, 166), "ILLUSTRATIVE SAMPLE — NOT YOUR MONEY", fill=(245, 185, 66), font=font(13, True))
    kpi(d, 40, 220, "SCORE", "56", ACCENT)
    kpi(d, 240, 220, "GRADE", "C", TEXT)
    kpi(d, 440, 220, "TER WASTE", "₹4,200/yr", DANGER)
    kpi(d, 640, 220, "OVERLAP", "₹3,100/yr", DANGER)
    card(d, (40, 340), (700, 160), "Top issue · Regular-plan TER leak", [
        "Switch eligible funds Direct to cut annual fee drag.",
        "L1 quant measured TER · L2 flagged has_ter_leak.",
        "LLM never invents the rupee number.",
    ], True)
    frames.append(save(img, "02_sample.png"))

    # 03 models
    img, d = base()
    d.text((40, 80), "STEP 03 · INTELLIGENCE", fill=ACCENT, font=font(14, True))
    d.text((40, 110), "L1 quant · L2 ML · L3 deep", fill=TEXT, font=font(34, True))
    card(d, (40, 200), (560, 280), "L2 ML · india_l2_v4", [
        "Bagged logistic + pure-Python GBM stumps",
        "38 features · temperature calibration",
        "Tasks: TER · overlap · concentration · tax ·",
        "liquidity · health score",
        "Cost: ₹0 · no sklearn / cloud GPU",
    ], True)
    card(d, (640, 200), (560, 280), "L3 DL + OCR v4", [
        "Fund embedding + style factors",
        "NAV sequence MLP",
        "Tesseract multi-PSM + AMFI lexicon",
        "633 free AMFI scheme seeds",
        "PDF / Excel / CSV / screenshot ingest",
    ])
    frames.append(save(img, "03_models.png"))

    # 04 upload
    img, d = base()
    d.text((40, 80), "STEP 04 · UPLOAD", fill=ACCENT, font=font(14, True))
    d.text((40, 110), "CAS · PDF · Excel · screenshot", fill=TEXT, font=font(34, True))
    formats = [".pdf", ".xlsx", ".csv", ".tsv", ".txt", ".json", ".png", ".jpg", ".webp"]
    x = 40
    for f in formats:
        tw = 90
        d.rounded_rectangle([x, 200, x + tw, 236], radius=12, fill=(20, 50, 70), outline=BORDER)
        d.text((x + 16, 208), f, fill=ACCENT, font=font(15, True))
        x += tw + 10
    card(d, (40, 280), (720, 200), "Universal free ingest", [
        "pdfminer · openpyxl · Tesseract · layout v4",
        "No paid OCR SaaS. Max 25MB local parse.",
        "Sample CSV → holdings → Health Check.",
        "Mobile Upload tab · web portal · /api/ingest/document",
    ], True)
    frames.append(save(img, "04_upload.png"))

    # 05 pay
    img, d = base()
    d.text((40, 80), "STEP 05 · PAY · UNLOCK", fill=ACCENT, font=font(14, True))
    d.text((40, 110), "Dummy ₹99 unlock path", fill=TEXT, font=font(34, True))
    card(d, (40, 210), (560, 240), "Order pay_demo", [
        "Amount ₹99 · method dummy_upi",
        "VPA nxance@okaxis (demo only)",
        "Status → paid",
        "Code NXANCE-PAID",
        "No real UPI charge in this build",
    ], True)
    card(d, (640, 210), (560, 240), "What unlocks", [
        "Full ranked issues",
        "L2 + L3 detail",
        "Holdings breakdown",
        "Or use DEMO-UNLOCK free",
        "",
    ])
    d.text((700, 380), "₹99", fill=OK, font=font(48, True))
    frames.append(save(img, "05_pay.png"))

    # 06 stack close
    img, d = base()
    d.text((40, 80), "STEP 06 · STACK", fill=ACCENT, font=font(14, True))
    d.text((40, 110), "World-class at ₹0", fill=TEXT, font=font(36, True))
    kpi(d, 40, 200, "COST", "₹0", OK)
    kpi(d, 240, 200, "AMFI", "633+", ACCENT)
    kpi(d, 440, 200, "L2", "v4", TEXT)
    kpi(d, 640, 200, "OCR", "v4", TEXT)
    card(d, (40, 320), (1100, 180), "Principle", [
        "LLM never computes returns, tax, or risk.",
        "Quant measures · ML scores · DL represents · language only explains.",
        "Android APK + web portal + FastAPI MBP — same navy system.",
        "Ohshn Intelligence · Palampur HP · Suggestion only",
    ], True)
    frames.append(save(img, "06_stack.png"))

    # 07 close
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 12, H], fill=ACCENT)
    d.rounded_rectangle([W // 2 - 36, 220, W // 2 + 36, 292], radius=14, fill=ACCENT)
    d.text((W // 2 - 12, 238), "N", fill=NAVY, font=font(36, True))
    d.text((W // 2 - 90, 320), "nxance", fill=TEXT, font=font(48, True))
    d.text((W // 2 - 260, 390), "Install APK · open /demo · DEMO-UNLOCK", fill=MUTED, font=font(22))
    d.text((W // 2 - 200, 450), "product/releases/  ·  Working demo ready", fill=ACCENT, font=font(20, True))
    frames.append(save(img, "07_close.png"))
    return frames


def png_to_clip(png: Path, mp4: Path, seconds: float):
    vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps=30"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(png),
            "-c:v", "libx264", "-t", str(seconds), "-pix_fmt", "yuv420p",
            "-vf", vf, "-an", str(mp4),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def assemble(frames: list[Path]):
    PARTS.mkdir(parents=True, exist_ok=True)
    for f in PARTS.glob("*.mp4"):
        f.unlink()
    durations = {
        "00_title": 3.0,
        "01_login": 4.0,
        "02_sample": 4.5,
        "03_models": 4.0,
        "04_upload": 4.0,
        "05_pay": 4.0,
        "06_stack": 4.0,
        "07_close": 3.5,
    }
    lines = []
    for png in frames:
        sec = durations.get(png.stem, 3.5)
        mp4 = PARTS / f"{png.stem}.mp4"
        print("clip", mp4.name, sec, flush=True)
        png_to_clip(png, mp4, sec)
        lines.append(f"file '{mp4.resolve()}'")
    concat = DEMO / "concat.txt"
    concat.write_text("\n".join(lines) + "\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(OUT)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    OUT_FULL.write_bytes(OUT.read_bytes())
    print("WROTE", OUT, OUT.stat().st_size, flush=True)
    print("WROTE", OUT_FULL, flush=True)


def main():
    frames = make_frames()
    assemble(frames)
    print("DONE")


if __name__ == "__main__":
    main()
