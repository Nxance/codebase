# Zero-cost ML · DL · OCR engine (v4)

**Cost: ₹0** — no paid APIs, no cloud GPU, no OCR SaaS, no sklearn/XGBoost binary deps.

## Stack

| Layer | Engine | Backend |
|-------|--------|---------|
| L1 | Quant (XIRR, TER, overlap, India metrics) | Pure Python |
| L2 | Bagged logistic / ridge **+ pure-Python GBM stumps** + temperature | `india_l2_v4` |
| L3 | Fund embedding + **style factors** + NAV sequence MLP + cluster overlap | `fund_embedding_v3` + style_v4 |
| OCR | Multi-preprocess → multi-PSM Tesseract → layout v4 → **AMFI lexicon** | System Tesseract + Pillow |

## Train (free compute)

```bash
cd product/mbp
source .venv/bin/activate
python training/scripts/train_worldclass_v4.py
# or full refresh including sequence MLP:
python training/scripts/train_worldclass_v3.py
python training/scripts/train_worldclass_v4.py
```

Artifacts: `training/models/india_l2_bundle_v4.json`, embeddings, `training/reports/worldclass_zero_cost_summary.json`.

## Quality bar (measured 2026-07-14)

| Metric | v3 | **v4 actual** |
|--------|----|---------------|
| Layout plaintext recall | 1.00 | **0.93** (stricter name match after lexicon) |
| Full OCR recall (synthetic screens) | 1.00 | **0.93** |
| Lexicon garble recovery | — | **1.00** (5/5 OCR garbles fixed) |
| L2 TER leak val acc | 0.97 | **0.974** |
| L2 overlap val acc | 0.99 | **1.00** |
| L2 concentration val acc | 0.95 | **0.96** |
| L2 tax_heavy val acc | 0.99 | **1.00** |
| Health score val MAE | 5.86 | **5.12** ↓ |
| Style overlap (Bluechip×Bluechip) | emb only | **blend 0.73 / style 1.0** |

> High synthetic accuracy is a floor for the free stack; replace with anonymised CAS over time for real-world lift.

## API

- `GET /api/training/status` — model bundle + boost + OCR readiness  
- `GET /api/deep/status` — embedding + sequence + style features  
- `POST /api/deep/overlap` — embedding×style fund pairs  
- `GET /api/ocr/status` — Tesseract readiness (v4)  
- `POST /api/ocr/image` — screenshot → `india_portfolio_v1`  
- `POST /api/ocr/text` — raw OCR text → holdings (+ lexicon)  

## Why this is “world-class at ₹0”

1. **No SaaS tax** — Tesseract + pure Python trainers; nothing that meters per page/API call.  
2. **Calibration** — temperature scaling + bag ensembles, not a single overfit logit.  
3. **Boost without bloat** — depth-1 GBM stumps in pure Python (portable JSON, no native wheels).  
4. **OCR that understands India apps** — multi-PSM + multi-preprocess + fund lexicon (AMFI + popular names).  
5. **DL that understands style** — BOW projection embeddings blended with free taxonomy factors (large/mid/small/index/ELSS/…).  
6. **Hard principle** — LLM never computes returns, tax, or risk.

## Principles

1. **LLM never computes** returns, tax, or risk.  
2. **Quant measures** (L1); **ML scores** (L2); **DL represents** (L3).  
3. Prefer free local tools (Tesseract, pure-Python trainers) over paid SaaS.  
4. Prefer **lazy loads** and compact JSON so the API survives low-RAM Macs (avoid SIGKILL on import).  
