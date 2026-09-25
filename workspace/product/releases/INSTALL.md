# Nxance — install & run the working demo

Same package shape as **Abhiyan** (`Mobile Apps/abhiyan/releases`): APK + live demo + product video.

## Contents

| Path | What |
|------|------|
| `Nxance-demo-debug.apk` | Android companion (login, upload, pay, health) |
| `demo_video/Nxance_Product_Demo.mp4` | Product walkthrough video |
| `demo_video/Nxance_Full_Owner_Demo.mp4` | Same full cut for owners |
| `CLIENT_DEMO.md` | 5-minute live demo script |
| `demo_video/DEMO_NARRATION.md` | Voiceover / scene list |

## 1. Start the API (Mac)

```bash
cd product/mbp
source .venv/bin/activate   # or: python3 -m venv .venv && pip install -r requirements.txt
./run.sh
# → http://127.0.0.1:8000
```

Live self-playing tour:

```
http://127.0.0.1:8000/demo
```

## 2. Install the APK

```bash
adb install -r product/releases/Nxance-demo-debug.apk
```

**Settings → API base URL**

- Emulator: `http://10.0.2.2:8000`
- Real phone (same Wi‑Fi): `http://<your-mac-lan-ip>:8000`

## 3. Demo unlock codes

- `DEMO-UNLOCK`
- `NXANCE-TEST`
- Dummy Pay tab → Create order → Confirm (no real UPI)

## 4. Rebuild the demo video

```bash
# API must be running
python3 product/releases/demo_video/record_and_assemble.py
```

Requires: Google Chrome, ffmpeg, Pillow (`pip install pillow`).

## 5. Formats for Upload

PDF · XLSX · CSV · TSV · TXT · JSON · PNG/JPG (OCR)

## Notes

- Suggestion only — not SEBI investment advice  
- Cost stack: ₹0 (Tesseract, pure-Python ML, free AMFI)  
- Ohshn Intelligence · Palampur HP  
