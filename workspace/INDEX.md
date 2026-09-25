# Nxance — searchable file index

**Phase status:** [CLOSEOUT.md](CLOSEOUT.md) — this build phase is **closed**.

Use **Cmd+F** / Ctrl+F. Tags help filtering by role.

---

## Root

| Path | What | Tags |
|------|------|------|
| [CLOSEOUT.md](CLOSEOUT.md) | Phase sign-off, deferred work | `closeout` `must-read` |
| [README.md](README.md) | Run map | `readme` |

---

## product/ — shippable code

| Path | What it is | Tags |
|------|------------|------|
| [`product/mbp/`](product/mbp/) | **MBP v2** — FastAPI + engines + premium UI | `code` `mbp` `run` |
| [`product/mobile/`](product/mobile/) | **Flutter Android** navy app | `mobile` `flutter` `navy` |
| [`product/web-portal/`](product/web-portal/) | **Marketing + web app** navy portal | `web` `portal` `navy` |
| [`product/shared/navy_palette.json`](product/shared/navy_palette.json) | Shared navy color palette | `design` `navy` |
| [`product/mbp/data/INDIA_DATA_PLATFORM.md`](product/mbp/data/INDIA_DATA_PLATFORM.md) | India schema, metrics, training, ingest map | `india` `data` `training` `must-read` |
| [`product/mbp/data/ZERO_COST_ML_DL_OCR.md`](product/mbp/data/ZERO_COST_ML_DL_OCR.md) | Zero-cost ML/DL/OCR design | `ml` `dl` `ocr` `zero-cost` |
| [`product/mbp/data/schemas/india_portfolio_v1.json`](product/mbp/data/schemas/india_portfolio_v1.json) | Canonical India portfolio schema | `india` `schema` |
| [`product/mbp/data/synthetic/`](product/mbp/data/synthetic/) | Multivariate training portfolios + features | `training` `synthetic` |
| [`product/mbp/training/models/india_l2_bundle.json`](product/mbp/training/models/india_l2_bundle.json) | Trained L2 model weights | `training` `ml` |
| [`product/mbp/README.md`](product/mbp/README.md) | How to run MBP | `code` `readme` |
| [`product/mbp/REQUIREMENTS_CORROBORATED.md`](product/mbp/REQUIREMENTS_CORROBORATED.md) | MBP scope vs zero-spend stack | `mbp` `spec` |
| [`product/mbp/app/main.py`](product/mbp/app/main.py) | API + guest demo endpoints | `code` `api` |
| [`product/mbp/app/engines/`](product/mbp/app/engines/) | HC · Construction · NxanceLM · Fraud · Guard | `code` `engines` |
| [`product/mbp/static/index.html`](product/mbp/static/index.html) | Product UI (value-first demo) | `code` `ui` |
| [`product/mbp/tests/test_engines.py`](product/mbp/tests/test_engines.py) | Engine smoke tests | `code` `test` |

---

## docs/00-start-here/

| Path | What it is | Tags |
|------|------------|------|
| [`docs/00-start-here/READING_ORDER.md`](docs/00-start-here/READING_ORDER.md) | Recommended path for founders / engineers / investors | `guide` |

---

## docs/01-product/ — definition & company

| Path | What it is | Tags |
|------|------------|------|
| [`docs/01-product/master-product-document.html`](docs/01-product/master-product-document.html) | Full product + screens + tech narrative | `product` `master` |
| [`docs/01-product/mvp-company-profile.html`](docs/01-product/mvp-company-profile.html) | Company / founder / financials profile | `product` `company` |
| [`docs/01-product/mbp-master-specification-v3.docx`](docs/01-product/mbp-master-specification-v3.docx) | **MBP rules** — 5×5 engines, questionnaire timing | `mbp` `spec` `must-read` |
| [`docs/01-product/mbp-complete-build-guide.docx`](docs/01-product/mbp-complete-build-guide.docx) | Definitive MBP build checklist | `mbp` `build` `must-read` |

---

## docs/02-engines/ — Health Check · Construction · NxanceLM

| Path | What it is | Tags |
|------|------------|------|
| [`docs/02-engines/health-check-architecture.html`](docs/02-engines/health-check-architecture.html) | HC engine architecture (full vision) | `engine` `health-check` |
| [`docs/02-engines/construction-engine-v3.html`](docs/02-engines/construction-engine-v3.html) | Construction + selection pipeline v3 | `engine` `construction` |
| [`docs/02-engines/nxancelm-engine.html`](docs/02-engines/nxancelm-engine.html) | NxanceLM modes & explainer role | `engine` `ai` |
| [`docs/02-engines/nxancelm-from-scratch.html`](docs/02-engines/nxancelm-from-scratch.html) | From-scratch LM vision (later phase) | `engine` `ai` `vision` |

---

## docs/03-technical/ — stack & architecture

| Path | What it is | Tags |
|------|------------|------|
| [`docs/03-technical/intelligence-architecture-rethink.md`](docs/03-technical/intelligence-architecture-rethink.md) | **Source of truth** — quant / ML / DL / optimise / language | `tech` `must-read` `architecture` `ml` `dl` |
| [`docs/03-technical/technical-brief.html`](docs/03-technical/technical-brief.html) | 10-min brief for engineers / CTOs | `tech` `brief` |
| [`docs/03-technical/complete-engineering-blueprint.html`](docs/03-technical/complete-engineering-blueprint.html) | Full engineering blueprint (older, vision-heavy) | `tech` `blueprint` |
| [`docs/03-technical/technology-complete-guide.html`](docs/03-technical/technology-complete-guide.html) | Tech choices + free tier path | `tech` `stack` `zero-cost` |
| [`docs/03-technical/technology-deep-dive.html`](docs/03-technical/technology-deep-dive.html) | Deeper stack / formulas / alternatives | `tech` `deep-dive` |

---

## docs/04-roadmap/ — phases & gates

| Path | What it is | Tags |
|------|------------|------|
| [`docs/04-roadmap/4-phase-roadmap.html`](docs/04-roadmap/4-phase-roadmap.html) | MVP → Beta → Phase 1 → Full Final | `roadmap` `phases` |
| [`docs/04-roadmap/technical-phase-plan.html`](docs/04-roadmap/technical-phase-plan.html) | Engineer-facing phase checklist | `roadmap` `tech` |

---

## docs/05-build-guides/ — how to build (historical guides)

| Path | What it is | Tags |
|------|------------|------|
| [`docs/05-build-guides/mvp-build-guide.html`](docs/05-build-guides/mvp-build-guide.html) | Week-by-week MVP guide | `build` `guide` |
| [`docs/05-build-guides/mvp-complete-build-guide.html`](docs/05-build-guides/mvp-complete-build-guide.html) | Complete guide with tech explanations | `build` `guide` |

> Prefer running **`product/mbp`** over re-following these from scratch; guides informed the MBP.

---

## docs/06-fundraising/ — pitch materials

| Path | What it is | Tags |
|------|------------|------|
| [`docs/06-fundraising/onepager-preseed-30L.pdf`](docs/06-fundraising/onepager-preseed-30L.pdf) | Pre-seed one-pager · ₹30L ask | `investor` `onepager` |
| [`docs/06-fundraising/onepager-preseed-75L.pdf`](docs/06-fundraising/onepager-preseed-75L.pdf) | Pre-seed one-pager · ₹75L ask | `investor` `onepager` |
| [`docs/06-fundraising/investor-accelerator-list.html`](docs/06-fundraising/investor-accelerator-list.html) | 100+ funds / angels / schemes | `investor` `targets` |

---

## docs/07-ux/ — design

| Path | What it is | Tags |
|------|------------|------|
| [`docs/07-ux/wireframes-v3-liquid-glass.html`](docs/07-ux/wireframes-v3-liquid-glass.html) | Mobile wireframes (liquid glass) | `ux` `wireframes` |

---

## prototypes/ — experiments (not the product)

| Path | What it is | Tags |
|------|------------|------|
| [`prototypes/live-data/backend.py`](prototypes/live-data/backend.py) | Early live AMFI Health Check API | `prototype` `api` |
| [`prototypes/live-data/frontend.html`](prototypes/live-data/frontend.html) | Matching simple frontend | `prototype` `ui` |
| [`prototypes/live-data/livedata-complete.zip`](prototypes/live-data/livedata-complete.zip) | Packaged live-data deploy | `prototype` `zip` |
| [`prototypes/interactive-demos/healthcheck-simple.html`](prototypes/interactive-demos/healthcheck-simple.html) | Simple HC page | `prototype` `ui` |
| [`prototypes/interactive-demos/portfolio-intelligence-v7.html`](prototypes/interactive-demos/portfolio-intelligence-v7.html) | v7 single-page HC+Construction demo | `prototype` `ui` |

---

## archive/ — duplicates & frozen packages

| Path | What it is | Tags |
|------|------------|------|
| [`archive/duplicates/`](archive/duplicates/) | Extra copies of build guides | `archive` |
| [`archive/packages/nxance-v3-final.zip`](archive/packages/nxance-v3-final.zip) | Old packaged bundle | `archive` `zip` |

---

## Tag legend

`must-read` · `mbp` · `code` · `product` · `engine` · `tech` · `roadmap` · `build` · `investor` · `ux` · `prototype` · `archive`
