#!/usr/bin/env python3
"""
Drive Nxance APK on Android emulator and capture screen-by-screen flow.

Prereqs:
  - emulator booted (adb devices shows emulator-*)
  - mock/real API on host :8000 (emulator reaches via 10.0.2.2:8000)
  - APK installed: adb install -r product/releases/Nxance-demo-debug.apk

Usage:
  python3 product/releases/demo_video/record_emulator_flow.py
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "emulator_frames"
PARTS = ROOT / "emulator_parts"
OUT_MP4 = ROOT / "Nxance_Emulator_HowTo.mp4"
PKG = "in.nxance.nxance_mobile"
API_HOST = "http://10.0.2.2:8000"

# Approximate Pixel-ish portrait coords (will be scaled from wm size)
# Order of bottom nav after login: Home, Health, Upload, Build, Pay
TABS = {
    "home": 0.10,
    "health": 0.30,
    "upload": 0.50,
    "build": 0.70,
    "pay": 0.90,
}


def log(m: str):
    print(m, flush=True)


def adb(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["adb", *args], check=check, capture_output=True, text=True)


def shell(cmd: str) -> str:
    r = adb("shell", cmd, check=False)
    return (r.stdout or "") + (r.stderr or "")


def wait_device(timeout: int = 120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = adb("devices", check=False)
        if "emulator" in r.stdout and "device" in r.stdout:
            boot = shell("getprop sys.boot_completed").strip()
            if boot == "1":
                log("emulator ready")
                return
        time.sleep(2)
    raise SystemExit("No booted emulator")


def wm_size() -> tuple[int, int]:
    out = shell("wm size")
    # Physical size: 1080x2400
    for line in out.splitlines():
        if "Physical size" in line or "Override size" in line or "size:" in line:
            part = line.split(":")[-1].strip()
            w, h = part.split("x")
            return int(w), int(h)
    return 1080, 2400


def tap(x: float, y: float, w: int, h: int):
    """x,y are fractions 0-1 of screen."""
    adb("shell", "input", "tap", str(int(x * w)), str(int(y * h)), check=False)
    time.sleep(0.6)


def tap_xy(px: int, py: int):
    adb("shell", "input", "tap", str(px), str(py), check=False)
    time.sleep(0.5)


def text(s: str):
    # escape spaces
    esc = s.replace(" ", "%s").replace("'", "")
    adb("shell", "input", "text", esc, check=False)
    time.sleep(0.3)


def key(code: str):
    adb("shell", "input", "keyevent", code, check=False)
    time.sleep(0.3)


def screencap(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    remote = "/sdcard/nx_cap.png"
    adb("shell", "screencap", "-p", remote, check=False)
    adb("pull", remote, str(path), check=False)
    if not path.exists() or path.stat().st_size < 1000:
        # fallback pipe
        raw = subprocess.run(
            ["adb", "exec-out", "screencap", "-p"],
            check=False,
            capture_output=True,
        )
        path.write_bytes(raw.stdout)
    log(f"  saved {path.name} ({path.stat().st_size // 1024} KB)")


def caption(src: Path, dst: Path, title: str):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(src).convert("RGB")
    # phone is tall — scale to 720 width for video consistency
    tw = 720
    th = int(img.height * (tw / img.width))
    img = img.resize((tw, th))
    # canvas with side talk
    W, H = 1400, 900
    canvas = Image.new("RGB", (W, H), (5, 11, 20))
    # fit phone into left
    max_h = H - 90
    max_w = 520
    scale = min(max_w / img.width, max_h / img.height)
    nw, nh = int(img.width * scale), int(img.height * scale)
    phone = img.resize((nw, nh))
    ox, oy = 60, (H - 70 - nh) // 2
    canvas.paste(phone, (ox, oy))
    d = ImageDraw.Draw(canvas)
    try:
        f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 26)
        fs = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
        fb = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 16)
    except Exception:
        f = fs = fb = ImageFont.load_default()
    d.text((620, 80), "EMULATOR FLOW", fill=(245, 185, 66), font=fb)
    d.text((620, 120), title, fill=(244, 248, 252), font=f)
    tips = {
        "01_login": "Enter name + phone → Continue\n(or Continue as guest)",
        "02_home": "Home hub: sample demo,\nHealth, Upload, Pay, Settings",
        "03_home_after": "API base is 10.0.2.2:8000\non emulator by default",
        "04_settings": "Settings → confirm API URL\nSave & test connection",
        "05_health": "Health tab → add holdings\nor run sample from Home",
        "06_upload": "Upload tab → pick PDF/CSV\nthen Run Health Check",
        "07_pay": "Pay tab → dummy ₹99 or\nDEMO-UNLOCK code",
        "08_build": "Build tab → goal questionnaire\n→ construction plan",
    }
    tip = tips.get(src.stem, "Nxance Android companion")
    y = 200
    for line in tip.split("\n"):
        d.text((620, y), line, fill=(155, 180, 204), font=fs)
        y += 32
    d.rectangle([0, H - 70, W, H], fill=(8, 16, 28))
    d.rectangle([0, H - 70, 8, H], fill=(61, 220, 255))
    d.text((20, H - 48), "HOW TO USE · ANDROID EMULATOR · INTERNAL", fill=(245, 185, 66), font=fb)
    d.text((20, H - 28), title, fill=(244, 248, 252), font=fs)
    dst.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dst)


def to_clip(png: Path, mp4: Path, sec: float = 5.0):
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(png),
            "-c:v", "libx264", "-t", str(sec), "-pix_fmt", "yuv420p",
            "-vf", "fps=30", "-an", str(mp4),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def install_apk():
    candidates = [
        ROOT.parent / "Nxance-demo-debug.apk",
        Path("/Users/bhaskar_pandey/Documents/Nxance/product/mobile/build/app/outputs/flutter-apk/app-debug.apk"),
    ]
    apk = next((p for p in candidates if p.exists()), None)
    if not apk:
        raise SystemExit("APK not found")
    log(f"install {apk}")
    adb("install", "-r", str(apk), check=False)


def launch_app():
    # force stop + launch main activity
    adb("shell", "am", "force-stop", PKG, check=False)
    time.sleep(0.5)
    adb(
        "shell",
        "am",
        "start",
        "-n",
        f"{PKG}/.MainActivity",
        check=False,
    )
    # flutter may use different activity name
    out = shell(f"monkey -p {PKG} -c android.intent.category.LAUNCHER 1")
    log("launched app")
    time.sleep(3.5)


def tab(name: str, w: int, h: int):
    # bottom nav y ~ 0.94 of height
    x = TABS[name]
    tap(x, 0.94, w, h)


def main():
    wait_device()
    w, h = wm_size()
    log(f"screen {w}x{h}")
    install_apk()
    launch_app()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cap_dir = OUT_DIR / "captioned"
    raw_dir = OUT_DIR / "raw"
    cap_dir.mkdir(exist_ok=True)
    raw_dir.mkdir(exist_ok=True)
    PARTS.mkdir(parents=True, exist_ok=True)
    for f in PARTS.glob("*.mp4"):
        f.unlink()

    shots: list[tuple[str, str, float]] = []

    # 01 Login screen (first frame of app)
    time.sleep(1.5)
    screencap(raw_dir / "01_login.png")
    shots.append(("01_login", "1 · Emulator login screen", 5.5))

    # Fill login: name field roughly mid, then phone, then Continue
    # Flutter TextFields — tap upper form area
    tap(0.5, 0.38, w, h)
    text("DemoInvestor")
    key("66")  # enter
    tap(0.5, 0.48, w, h)
    text("9876500001")
    # Continue primary button ~ 0.58-0.62
    tap(0.5, 0.58, w, h)
    time.sleep(2.0)
    screencap(raw_dir / "02_home.png")
    shots.append(("02_home", "2 · Home after login", 5.5))

    # Open Settings via Home button if visible (bottom of list) — tap lower outlined button
    # Settings is often last row ~ 0.78
    tap(0.75, 0.78, w, h)  # try Settings half of row
    time.sleep(1.5)
    # If still on home, open via scrolling not available — use tab Home then scroll not easy
    screencap(raw_dir / "03_settings_or_home.png")
    shots.append(("03_home_after", "3 · Post-login hub / settings", 5.0))

    # Health tab
    tab("health", w, h)
    time.sleep(1.2)
    screencap(raw_dir / "05_health.png")
    shots.append(("05_health", "4 · Health tab — holdings entry", 5.5))

    # Upload tab
    tab("upload", w, h)
    time.sleep(1.2)
    screencap(raw_dir / "06_upload.png")
    shots.append(("06_upload", "5 · Upload tab — CAS / PDF / Excel", 5.5))

    # Build tab
    tab("build", w, h)
    time.sleep(1.2)
    screencap(raw_dir / "08_build.png")
    shots.append(("08_build", "6 · Build tab — construction", 5.0))

    # Pay tab
    tab("pay", w, h)
    time.sleep(1.2)
    screencap(raw_dir / "07_pay.png")
    shots.append(("07_pay", "7 · Pay tab — dummy unlock", 5.5))

    # Back to home
    tab("home", w, h)
    time.sleep(1.0)
    screencap(raw_dir / "09_home_final.png")
    shots.append(("02_home", "8 · Back to Home — ready to demo", 4.5))

    lines = []
    for stem, title, sec in shots:
        raw = raw_dir / f"{stem if (raw_dir / f'{stem}.png').exists() else stem}.png"
        # map for captioned names unique
        # find actual file
        candidates = list(raw_dir.glob(f"{stem}*.png")) or list(raw_dir.glob("*.png"))
        # use ordered files
    # Build clips in capture order
    ordered = sorted(raw_dir.glob("*.png"))
    # Prefer explicit sequence
    seq = [
        "01_login.png",
        "02_home.png",
        "03_settings_or_home.png",
        "05_health.png",
        "06_upload.png",
        "08_build.png",
        "07_pay.png",
        "09_home_final.png",
    ]
    titles = {
        "01_login.png": ("1 · Emulator: Login", 5.5),
        "02_home.png": ("2 · Emulator: Home hub", 5.5),
        "03_settings_or_home.png": ("3 · Emulator: After login", 5.0),
        "05_health.png": ("4 · Emulator: Health tab", 5.5),
        "06_upload.png": ("5 · Emulator: Upload tab", 5.5),
        "08_build.png": ("6 · Emulator: Build tab", 5.0),
        "07_pay.png": ("7 · Emulator: Pay / unlock", 5.5),
        "09_home_final.png": ("8 · Emulator: Home ready", 4.5),
    }
    for name in seq:
        src = raw_dir / name
        if not src.exists():
            log(f"missing {name}, skip")
            continue
        cpath = cap_dir / name
        title, sec = titles[name]
        caption(src, cpath, title)
        mp4 = PARTS / (name.replace(".png", ".mp4"))
        to_clip(cpath, mp4, sec)
        lines.append(f"file '{mp4.resolve()}'")

    concat = ROOT / "concat_emulator.txt"
    concat.write_text("\n".join(lines) + "\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(OUT_MP4)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    log(f"WROTE {OUT_MP4} ({OUT_MP4.stat().st_size // 1024} KB)")

    # Merge with web walkthrough if present
    web = ROOT / "Nxance_HowTo_Use_Internal.mp4"
    merged = ROOT / "Nxance_Full_Team_Walkthrough.mp4"
    if web.exists() and lines:
        bridge = PARTS / "bridge.mp4"
        # simple 2s black bridge with text via caption of solid
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (1400, 900), (10, 22, 40))
        d = ImageDraw.Draw(img)
        try:
            f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 40)
        except Exception:
            f = ImageFont.load_default()
        d.text((120, 400), "Next: Android emulator flow", fill=(61, 220, 255), font=f)
        bp = cap_dir / "bridge.png"
        img.save(bp)
        to_clip(bp, bridge, 2.5)
        mconcat = ROOT / "concat_full_team.txt"
        mconcat.write_text(
            f"file '{web.resolve()}'\nfile '{bridge.resolve()}'\nfile '{OUT_MP4.resolve()}'\n"
        )
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(mconcat), "-c", "copy", str(merged)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        shutil.copy2(merged, ROOT / "Nxance_Product_Demo.mp4")
        log(f"WROTE {merged}")
        log("Also updated Nxance_Product_Demo.mp4 (web + emulator)")


if __name__ == "__main__":
    main()
