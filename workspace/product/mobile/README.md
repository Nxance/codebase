# Nxance Flutter (Android)

Navy mobile app wired to the MBP API.

## Screens

| Tab | Features |
|-----|----------|
| **Home** | Value prop, sample demo CTA |
| **Health** | Manual holdings, sample rows, diagnosis, issues, unlock |
| **Build** | SIP/years/risk sliders, allocation + instruments |
| **Ask** | NxanceLM chat (number-guarded) |
| **Settings** | API base URL, connection + training status |

## Run

```bash
# Terminal 1 — API
cd ../mbp && ./run.sh

# Terminal 2 — Android
cd ../mobile
flutter pub get
flutter run
```

### API host

| Environment | Base URL |
|-------------|----------|
| Android emulator | `http://10.0.2.2:8000` (default) |
| Physical device | `http://<your-mac-lan-ip>:8000` in Settings |

Cleartext HTTP is enabled for local dev (`usesCleartextTraffic`).

## Unlock codes

`DEMO-UNLOCK` · `NXANCE-TEST`
