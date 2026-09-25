#!/usr/bin/env python3
"""Capture how-to-use walkthrough per step (?step=N) → internal training video."""
from __future__ import annotations

import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRAMES = ROOT / "howto_frames"
PARTS = ROOT / "howto_parts"
OUT = ROOT / "Nxance_HowTo_Use_Internal.mp4"
API = "http://127.0.0.1:8765"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H = 1400, 900

STEPS = [
    (1, "01_login", 6.0, "1 · Login — name + phone or guest"),
    (2, "02_home", 6.0, "2 · Home hub — sample vs real path"),
    (3, "03_sample_health", 6.5, "3 · Sample Health — labelled demo, not user money"),
    (4, "04_manual_health", 6.0, "4 · Own holdings path — analyse or load rows"),
    (5, "05_upload", 6.5, "5 · Upload CAS / PDF / Excel / screenshot"),
    (6, "06_pay", 6.5, "6 · Dummy pay or DEMO-UNLOCK"),
    (7, "07_settings", 6.0, "7 · Settings — API URL + model status"),
    (8, "08_recap", 6.0, "8 · Team recap — full flow"),
]


def log(m):
    print(m, flush=True)


def wait_api():
    for _ in range(30):
        try:
            with urllib.request.urlopen(API + "/api/health", timeout=3) as r:
                if r.status == 200:
                    log("API ready " + API)
                    return
        except Exception:
            pass
        time.sleep(1)
    raise SystemExit("Demo server not on 8765")


def shot(url: str, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        f"--window-size={W},{H}",
        "--virtual-time-budget=8000",
        f"--screenshot={path}",
        url,
    ]
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not path.exists() or path.stat().st_size < 2000:
        alt = Path("screenshot.png")
        if alt.exists():
            shutil.move(str(alt), str(path))
    if not path.exists():
        raise RuntimeError("shot failed " + str(path))


def caption(src: Path, dst: Path, text: str):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(src).convert("RGB").resize((W, H))
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
        fs = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 15)
    except Exception:
        f = fs = ImageFont.load_default()
    d.rectangle([0, H - 70, W, H], fill=(5, 11, 20))
    d.rectangle([0, H - 70, 8, H], fill=(61, 220, 255))
    d.text((18, H - 52), "HOW TO USE · INTERNAL TEAM", fill=(245, 185, 66), font=fs)
    d.text((18, H - 32), text, fill=(244, 248, 252), font=f)
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst)


def clip(png: Path, mp4: Path, sec: float):
    vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps=30"
    subprocess.run(
        ["ffmpeg", "-y", "-loop", "1", "-i", str(png), "-c:v", "libx264",
         "-t", str(sec), "-pix_fmt", "yuv420p", "-vf", vf, "-an", str(mp4)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def main():
    wait_api()
    raw = FRAMES / "raw"
    cap = FRAMES / "captioned"
    raw.mkdir(parents=True, exist_ok=True)
    cap.mkdir(parents=True, exist_ok=True)
    PARTS.mkdir(parents=True, exist_ok=True)
    for f in PARTS.glob("*.mp4"):
        f.unlink()
    lines = []
    for n, name, sec, text in STEPS:
        url = f"{API}/how-to-use?step={n}"
        rpath = raw / f"{name}.png"
        cpath = cap / f"{name}.png"
        log(f"capture step {n} {name}")
        shot(url, rpath)
        caption(rpath, cpath, text)
        mpath = PARTS / f"{name}.mp4"
        clip(cpath, mpath, sec)
        lines.append(f"file '{mpath.resolve()}'")
    concat = ROOT / "concat_howto.txt"
    concat.write_text("\n".join(lines) + "\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(OUT)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    shutil.copy2(OUT, ROOT / "Nxance_Product_Demo.mp4")
    shutil.copy2(OUT, ROOT / "Nxance_Full_Owner_Demo.mp4")
    log(f"WROTE {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
