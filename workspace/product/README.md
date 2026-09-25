# Nxance product surface

| Path | What |
|------|------|
| **[mbp/](mbp/)** | Core FastAPI intelligence API + engines + training |
| **[mobile/](mobile/)** | **Flutter Android** app (navy) |
| **[web-portal/](web-portal/)** | **Marketing site + web app shell** (navy) |
| **[shared/navy_palette.json](shared/navy_palette.json)** | Shared navy color tokens |

## Navy palette (base)

| Token | Hex |
|-------|-----|
| Navy 900 (bg) | `#0A1628` |
| Navy 800 | `#0F2744` |
| Navy 700 | `#163A5F` |
| Accent cyan | `#3DDCFF` |
| Text | `#F4F8FC` |

## Run API

```bash
cd mbp && ./run.sh
# http://127.0.0.1:8000
```

## Run Flutter (Android)

```bash
cd mobile
flutter pub get
# emulator API host is 10.0.2.2:8000 in lib/api/client.dart
flutter run
```

## Open web portal

```bash
# with API already running:
open web-portal/index.html
# or serve statically:
cd web-portal && python3 -m http.server 5500
# http://127.0.0.1:5500
```

Set API base: `localStorage.setItem('nx_api','http://127.0.0.1:8000')`

## Deep models

```bash
cd mbp
source .venv/bin/activate
python3 training/scripts/train_deep_models.py
# produces training/models/fund_embedding_v1.json + nav_sequence_v1.json
```
