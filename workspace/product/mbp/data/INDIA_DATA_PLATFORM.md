# India data & training platform

## Purpose

Prepare Nxance for **every Indian report path** (CAS, broker CSV, OCR, web) on one schema, expand **India quant metrics**, generate **multivariate training data**, and train **L2 models** that plug into production.

## Layout

```
product/mbp/
  data/
    schemas/
      india_portfolio_v1.json      # canonical portfolio JSON Schema
      india_report_sources.md      # CDSL/NSDL/CAMS/KFin/brokers map
    india/
      amfi_seed_funds.json         # live AMFI seed list (downloaded)
      nav_history_sample_*.json    # sample NAV history shape
    synthetic/
      portfolios_train.jsonl       # full synthetic portfolios + labels
      portfolios_val.jsonl
      features_train.csv           # ML feature matrix
      features_val.csv
      labels_meta.json
    INDIA_DATA_PLATFORM.md         # this file
  training/
    scripts/
      generate_synthetic_india.py
      train_india_models.py
    models/
      india_l2_bundle.json         # production-loadable weights
    reports/
      train_report.json
  app/intelligence/
    quant/india_metrics.py         # tax, sector, liquidity, FD post-tax, SIP…
    ingest/                        # CSV / CAS text / OCR → schema
    ml/trained.py                  # load bundle at runtime
```

## Canonical schema: `india_portfolio_v1`

Every ingest channel must emit:

- `source.channel` — `cas_cdsl` | `cas_cams` | `broker_zerodha` | `ocr_screenshot` | …
- `lots[]` — ISIN/AMFI/folio/plan/qty/cost/value/dates/tax fields  
- optional `cashflows[]` — SIPs for true XIRR  

Engines convert lots → internal holdings via `ingest/canonical.py`.

## India quant metrics (beyond XIRR/TER/overlap)

| Metric | Why it matters in India |
|--------|-------------------------|
| Tax bucket STCG/LTCG/debt/ELSS | Exit tax awareness |
| Est. tax if sold | Switch cost before “fix” |
| Sector concentration | Financials/IT heavy books |
| Market-cap mix | Smallcap risk after 2023–24 flows |
| Direct vs Regular AUM % | Cost culture |
| Liquidity / lock-in score | ELSS 3y, PPF, NPS, FD |
| FD post-tax yield | Compare to debt funds fairly |
| SIP regularity | Behaviour / goal probability |

## Training pipeline

```bash
cd product/mbp
source .venv/bin/activate

# 1) Multivariate dummy India portfolios (1000 default)
python3 training/scripts/generate_synthetic_india.py 800 200

# 2) Train L2 logistic + ridge models → training/models/india_l2_bundle.json
python3 training/scripts/train_india_models.py

# 3) Status API
# GET /api/training/status
```

### Labels trained

- `has_ter_leak`, `has_overlap`, `high_concentration`, `tax_heavy`, `low_liquidity` (logistic)  
- `health_score` (ridge regression)  

### Features

See `INDIA_FEATURE_COLUMNS` in `india_metrics.py` / `labels_meta.json`.

## Ingest paths (same schema)

| Path | Module | Status |
|------|--------|--------|
| CSV / broker export | `ingest/csv_map.py` | Fuzzy headers ready |
| CAS plain text | `ingest/cas_stub.py` | Pattern stub → full PDF next |
| OCR text | `ingest/ocr_stub.py` | Text in; OCR engine pluggable |
| Account Aggregator | — | Channel reserved in schema |

API:

- `POST /api/parse-excel` (CSV → canonical + holdings)  
- `POST /api/ingest/cas-text`  
- `POST /api/ingest/ocr-text`  
- `GET /api/training/status`  

## Production health pipeline now uses

1. L1 classic quant (XIRR, TER, overlap, MC)  
2. **L1 India metrics** (sector, tax, liquidity, plan mix)  
3. L2 prior scorer + **trained India bundle** (if present)  
4. Guidance issues from both economic leaks and India flags  

## Next real-data upgrades (when available)

1. Anonymised CAS corpus (user-consented) replacing synthetic labels  
2. Nightly AMFI NAV panel for all schemes in seed list  
3. Full PDF CAS unlock (PAN password) with pdfplumber  
4. Tesseract/PaddleOCR for Groww/Zerodha screenshots  
5. LightGBM once Python/sklearn wheels stable on your runtime  

## Principle

**One India schema. Many doors in. Quant + ML trained on that shape. OCR and web are just more doors.**
