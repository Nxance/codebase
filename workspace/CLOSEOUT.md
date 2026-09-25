# Nxance — Phase closeout (2026-07-13)

**Status: CLOSED for this build phase**  
Everything intended for this sprint is delivered, documented, and runnable.  
What is left is **next-phase** work (production CAS, payments, store release) — not unfinished scaffolding.

---

## 1. Decision

| Question | Answer |
|----------|--------|
| Can we demo today? | **Yes** |
| Can friends test on web? | **Yes** (with API running) |
| Can Android run on emulator? | **Yes** (`flutter run`) |
| Public production / strangers paying at scale? | **Next phase** — see §5 |

**This phase is closed.** Do not keep expanding scope without a new phase plan.

---

## 2. What was delivered

### Product code
| Path | Deliverable |
|------|-------------|
| `product/mbp/` | FastAPI MBP: Health Check, Construction, NxanceLM, unlock, ingest stubs |
| `product/mbp/app/intelligence/` | L1 quant + India metrics, L2 ML, L3 deep, L4 optimise, L5 NLP, pipelines |
| `product/mbp/data/` | India schema, synthetic training set, AMFI seeds |
| `product/mbp/training/` | L2 + L3 trained model bundles |
| `product/mobile/` | Flutter Android navy app (5 tabs) |
| `product/web-portal/` | Navy marketing + app portal |
| `product/shared/navy_palette.json` | Shared design tokens |

### Workspace
| Path | Role |
|------|------|
| `README.md` | Entry map |
| `INDEX.md` | Searchable catalog |
| `docs/` | Specs, engines, roadmap, fundraising (organised) |
| `prototypes/` | Old demos (historical) |
| `archive/` | Duplicates / zips |
| `CLOSEOUT.md` | This file |

### Intelligence stack (frozen for this phase)
```
L1 quant → L1 India → L2 ML (trained) → L3 deep (embeddings + sequence)
         → L4 optimise (construction) → L5 language + Number Guard
```

---

## 3. How to run (day after close)

### API
```bash
cd product/mbp
./run.sh
# http://127.0.0.1:8000
```

### Web portal
```bash
cd product/web-portal
python3 -m http.server 5500
# http://127.0.0.1:5500
```

### Android
```bash
# API must be running first
cd product/mobile
flutter pub get
flutter run
# Emulator API: http://10.0.2.2:8000  (Settings tab)
```

### Unlock (demo)
`DEMO-UNLOCK` · `NXANCE-TEST`

### Re-train (optional)
```bash
cd product/mbp && source .venv/bin/activate
python3 training/scripts/generate_synthetic_india.py 800 200
python3 training/scripts/train_india_models.py
python3 training/scripts/train_deep_models.py
```

---

## 4. Verification checklist (done this phase)

- [x] Engine unit tests (pipeline adapters)
- [x] Sample demo does **not** claim personal loss without data
- [x] India schema + synthetic multivariate data generated
- [x] L2 + L3 model files present and loadable via API
- [x] Flutter app structure (Home / Health / Build / Ask / Settings)
- [x] Web portal marketing + app shell
- [x] Folder searchable via README + INDEX

---

## 5. Explicitly deferred (next phase — not “unfinished today”)

| Item | Why deferred |
|------|----------------|
| Full CAS PDF unlock (CDSL/NSDL/CAMS) | Parser production quality |
| Real OCR pipeline binary | Needs Tesseract/cloud + UX |
| Razorpay live | Business KYC + webhooks |
| Production HTTPS host | Deploy choice (Railway etc.) |
| Play Store listing | Icons, signing, policy pages |
| Real-user ML retraining | Needs consented CAS corpus |
| iOS Flutter target | Android first by decision |
| SEBI/legal review | External |

**Next phase open only when you start a new sprint.** Suggested first tickets:
1. Host API with HTTPS  
2. CAS PDF path v1  
3. Razorpay test mode  
4. Play internal testing  

---

## 6. Source of truth priority (after close)

1. `docs/03-technical/intelligence-architecture-rethink.md`  
2. `product/mbp/` (running code)  
3. `product/mbp/data/INDIA_DATA_PLATFORM.md`  
4. `docs/01-product/*mbp*` specs  
5. Older HTML engine docs = vision only  

---

## 7. Sign-off

| Role | Outcome |
|------|---------|
| Engineering (this phase) | **Closed** — demos, apps, models, structure shipped |
| Product (buyable public MBP) | **Open next phase** — parse + pay + host |
| Fundraising materials | Present in `docs/06-fundraising/` (unchanged content) |

**Closed on:** 2026-07-13  
**Brand:** Nxance · Ohshn Intelligence · Palampur, HP  
