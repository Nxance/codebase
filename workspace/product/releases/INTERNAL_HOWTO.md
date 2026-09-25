# Nxance — internal how-to (web + emulator)

## Watch (recommended for team meeting)

```bash
open product/releases/demo_video/Nxance_Full_Team_Walkthrough.mp4
# or
open product/releases/demo_video/Nxance_Product_Demo.mp4
```

**Part 1** — Phone mock + coach talk track (8 screens: Login → Recap)  
**Part 2** — **Real Android emulator** APK (Home · Health · Upload · Build · Pay · Settings)

## Emulator-only cut

```bash
open product/releases/demo_video/Nxance_Emulator_HowTo.mp4
```

## Live interactive (browser)

```bash
open http://127.0.0.1:8765/how-to-use
```

## Live emulator yourself

```bash
# API for emulator (host:8000 → 10.0.2.2:8000)
# Start mock or full MBP on :8000

export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
export PATH="$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools:$PATH"
emulator -avd nxance_pixel &
adb install -r product/releases/Nxance-demo-debug.apk
adb shell am start -n in.nxance.nxance_mobile/.MainActivity
```

**Settings → API base URL:** `http://10.0.2.2:8000`

## Rebuild emulator capture

```bash
# emulator booted + API on :8000
python3 product/releases/demo_video/record_emulator_flow.py
```

## Codes

`DEMO-UNLOCK` · `NXANCE-TEST` · dummy Pay confirm
