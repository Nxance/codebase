# Nxance full owner demo guide

Mirrors the Abhiyan release package under `Mobile Apps/abhiyan/releases/`.

## Deliverables

1. **Live tour** — `http://127.0.0.1:8000/demo`  
2. **Product video** — `Nxance_Product_Demo.mp4`  
3. **APK** — `../Nxance-demo-debug.apk`  
4. **Docs** — `../INSTALL.md`, `../CLIENT_DEMO.md`, `DEMO_NARRATION.md`

## Rebuild video after UI changes

```bash
# terminal 1
cd product/mbp && source .venv/bin/activate && ./run.sh

# terminal 2
python3 product/releases/demo_video/record_and_assemble.py
```

## Capture map

Written to `capture_map.json` after each run (API URL + frame list).

## Difference vs Abhiyan

| Abhiyan | Nxance |
|---------|--------|
| Field / polls / war room | Health / upload / pay / ML stack |
| Firebase demo | FastAPI local MBP |
| Party CMS cards | ₹0 intelligence stack cards |

Same assembly idea: pitch cards + live screenshots + ffmpeg concat.
