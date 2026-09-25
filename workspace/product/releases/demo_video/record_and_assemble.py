#!/usr/bin/env python3
"""
Nxance live demo capture + assemble (Abhiyan-style).

1. Hits live FastAPI /demo tour (self-playing, real engines)
2. Captures timed screenshots via headless Chrome
3. Builds pitch cards with Pillow
4. Assembles Nxance_Product_Demo.mp4 with ffmpeg

Usage:
  python3 product/releases/demo_video/record_and_assemble.py
  # optional:
  API=http://127.0.0.1:8000 python3 .../record_and_assemble.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # product/
DEMO_DIR = Path(__file__).resolve().parent
FRAMES = DEMO_DIR / "frames"
COMPOSED = DEMO_DIR / "composed"
CARDS = DEMO_DIR / "pitch_cards"
OUT_MP4 = DEMO_DIR / "Nxance_Product_Demo.mp4"
OUT_FULL = DEMO_DIR / "Nxance_Full_Owner_Demo.mp4"
API = os.environ.get("API", "http://127.0.0.1:8000").rstrip("/")
CHROME = os.environ.get(
    "CHROME",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
W, H = 1280, 800
DWELL = float(os.environ.get("DWELL", "4.5"))  # seconds per tour beat
FPS = 30


def log(msg: str):
    print(msg, flush=True)


def ensure_dirs():
    for d in (FRAMES, COMPOSED, CARDS, DEMO_DIR / "assemble_parts"):
        d.mkdir(parents=True, exist_ok=True)


def wait_api(timeout: float = 90.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(API + "/api/health", timeout=3) as r:
                if r.status == 200:
                    log(f"API ready at {API}")
                    return
        except Exception:
            pass
        time.sleep(1.5)
    raise SystemExit(f"API not reachable at {API} — start product/mbp ./run.sh first")


def chrome_shot(url: str, out: Path, wait_ms: int = 2500):
    out.parent.mkdir(parents=True, exist_ok=True)
    # Chrome writes screenshot.png next to cwd unless path given; use absolute
    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={W},{H}",
        f"--virtual-time-budget={wait_ms}",
        f"--screenshot={out}",
        url,
    ]
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not out.exists() or out.stat().st_size < 1000:
        # fallback name chrome sometimes uses
        alt = Path("screenshot.png")
        if alt.exists():
            shutil.move(str(alt), str(out))
    if not out.exists():
        raise RuntimeError(f"Screenshot failed for {url} → {out}")


def make_pitch_cards():
    from PIL import Image, ImageDraw, ImageFont

    try:
        font_lg = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 54)
        font_md = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 28)
        font_sm = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    except Exception:
        font_lg = font_md = font_sm = ImageFont.load_default()

    cards = [
        ("00_title.png", "nxance", "Portfolio intelligence for India", "LIVE WORKING DEMO · ₹0 STACK"),
        ("01_bridge.png", "What you will see", "Login → Sample health → ML/DL → Upload → Pay", "Real FastAPI engines · not mockups"),
        ("90_close.png", "Install & try", "APK + web portal + DEMO-UNLOCK", "product/releases/"),
    ]
    for name, title, sub, foot in cards:
        img = Image.new("RGB", (W, H), (10, 22, 40))
        d = ImageDraw.Draw(img)
        # accent bar
        d.rectangle([0, 0, 12, H], fill=(61, 220, 255))
        d.text((64, H // 2 - 90), title, fill=(244, 248, 252), font=font_lg)
        d.text((64, H // 2 - 10), sub, fill=(155, 180, 204), font=font_md)
        d.text((64, H // 2 + 50), foot, fill=(61, 220, 255), font=font_sm)
        img.save(CARDS / name)
        log(f"  card {name}")


def capture_live_tour():
    """
    Capture tour by reloading /demo with increasing virtual time so each
    step of the self-playing tour is visible, then one full dwell shot.
    """
    # Beats match demo_tour.html ~4.2s each + load
    beats = [
        ("01_login", 3_500),
        ("02_sample", 8_500),
        ("03_models", 13_500),
        ("04_upload", 18_500),
        ("05_pay", 23_500),
        ("06_stack", 28_500),
        ("07_close", 33_500),
    ]
    for name, budget in beats:
        out = FRAMES / f"{name}.png"
        log(f"  capture {name} vt={budget}ms")
        chrome_shot(f"{API}/demo", out, wait_ms=budget)
        # small real wait so API is not hammered
        time.sleep(0.4)
    # also capture main product UI
    chrome_shot(f"{API}/", FRAMES / "00_home.png", wait_ms=2000)
    log("  capture 00_home")


def png_to_clip(png: Path, mp4: Path, seconds: float = 3.5):
    mp4.parent.mkdir(parents=True, exist_ok=True)
    # scale/pad to exact WxH, hold still
    vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS}"
    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(png),
        "-c:v",
        "libx264",
        "-t",
        str(seconds),
        "-pix_fmt",
        "yuv420p",
        "-vf",
        vf,
        "-an",
        str(mp4),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def assemble():
    parts = DEMO_DIR / "assemble_parts"
    parts.mkdir(exist_ok=True)
    # clear old
    for f in parts.glob("*.mp4"):
        f.unlink()

    sequence = [
        (CARDS / "00_title.png", "00_title.mp4", 3.0),
        (CARDS / "01_bridge.png", "01_bridge.mp4", 3.0),
        (FRAMES / "00_home.png", "tour_00_home.mp4", 3.0),
        (FRAMES / "01_login.png", "tour_01_login.mp4", 4.0),
        (FRAMES / "02_sample.png", "tour_02_sample.mp4", 4.5),
        (FRAMES / "03_models.png", "tour_03_models.mp4", 4.0),
        (FRAMES / "04_upload.png", "tour_04_upload.mp4", 4.0),
        (FRAMES / "05_pay.png", "tour_05_pay.mp4", 4.0),
        (FRAMES / "06_stack.png", "tour_06_stack.mp4", 3.5),
        (FRAMES / "07_close.png", "tour_07_close.mp4", 3.5),
        (CARDS / "90_close.png", "90_close.mp4", 3.0),
    ]

    concat_lines = []
    for png, name, sec in sequence:
        if not png.exists():
            log(f"  skip missing {png.name}")
            continue
        mp4 = parts / name
        log(f"  clip {name} ({sec}s)")
        png_to_clip(png, mp4, sec)
        # also copy composed pair
        shutil.copy2(png, COMPOSED / (png.stem + ".png"))
        shutil.copy2(mp4, COMPOSED / (png.stem + ".mp4"))
        concat_lines.append(f"file '{mp4.resolve()}'")

    concat_path = DEMO_DIR / "concat.txt"
    concat_path.write_text("\n".join(concat_lines) + "\n")
    log("Concatenating…")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c",
            "copy",
            str(OUT_MP4),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    shutil.copy2(OUT_MP4, OUT_FULL)
    log(f"Wrote {OUT_MP4} ({OUT_MP4.stat().st_size // 1024} KB)")
    log(f"Wrote {OUT_FULL}")


def write_map():
    (DEMO_DIR / "capture_map.json").write_text(
        json.dumps(
            {
                "api": API,
                "demo_url": f"{API}/demo",
                "frames": sorted(p.name for p in FRAMES.glob("*.png")),
                "output": str(OUT_MP4.name),
            },
            indent=2,
        )
    )


def main():
    if not Path(CHROME).exists():
        raise SystemExit(f"Chrome not found at {CHROME}")
    ensure_dirs()
    wait_api()
    # verify demo route
    try:
        with urllib.request.urlopen(API + "/demo", timeout=10) as r:
            if r.status != 200:
                raise SystemExit("/demo not available — restart API after pull")
    except Exception as e:
        raise SystemExit(f"/demo failed: {e}")

    log("=== Pitch cards ===")
    make_pitch_cards()
    log("=== Live tour capture ===")
    capture_live_tour()
    log("=== Assemble video ===")
    assemble()
    write_map()
    log("=== DONE ===")
    log(f"Open: {OUT_MP4}")


if __name__ == "__main__":
    main()
