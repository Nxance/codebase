# Nxance — How We Actually Build This
### Consolidated from the v3.1 engine specs, the backend spec, the working skeleton, and MIT's Quant Bible

---

## 0. The one decision this whole document is built around

We are **not** training our own foundation model from scratch to launch. That's a multi-crore, multi-year R&D program — not something a pre-funding startup does for v1. Almost no fintech company does this, including large ones.

Instead:

- **Everything that calculates a number** — health scores, XIRR, risk, allocations, Monte Carlo probabilities, the 16-layer FIT score, tax logic, rebalancing — is **plain Python/Rust code**. Formulas from real quant finance (Markowitz, Black-Litterman, Bayesian stats), not AI. This is 90% of the product and it needs **zero AI** to work.
- **NxanceLM (the chat/narration layer)** runs on an **existing model** — either a commercial API (Claude/GPT, pay-per-token) or a small **open-source model we fine-tune ourselves** (Llama/Mistral/Qwen-class, 7B–8B) on India-specific financial data (SEBI circulars, AMFI data, RBI communications, our own engine outputs). Either way, we are not inventing a new base model — we are prompting or fine-tuning one that already exists.
- **Number Guard is the rule that makes this safe**: the AI is *never* allowed to compute or invent a number. It only ever explains numbers the deterministic engines already produced. If the AI's output contains a number that doesn't trace back to an engine result, it gets rejected and regenerated. This is a real, testable piece of code (`engines/shared/number_guard.py`), not a slogan.

This means: **the entire quant core (both 26-engine systems) can be built, tested, and demoed today with zero LLM cost and zero LLM dependency.** The AI is the last 10%, bolted on at the end, and it can be cheap or free (self-hosted open model) if we want it to be.

Everything below assumes this split.

---

## 1. System architecture — one picture

```
                    ┌───────────────────────────────┐
                    │   DATA LAYER (runs nightly)     │
                    │  NSE/BSE, AMFI, RBI, news feeds  │
                    │  → cleaned → scored → Postgres    │
                    └────────────────┬─────────────────┘
                                      │
      ┌───────────────────────────────┼───────────────────────────────┐
      │                                 │                                 │
┌─────▼──────────┐          ┌──────────▼───────────┐          ┌─────────▼────────┐
│ HEALTH CHECK      │          │ CONSTRUCTION            │          │ TERMINAL             │
│ ENGINE            │          │ ENGINE                  │          │ (market dashboard)     │
│ 26 sub-engines     │          │ 26 sub-engines           │          │ reads data layer        │
│ diagnose→advise→   │          │ build→manage             │          │ directly — no AI,        │
│ manage             │          │                          │          │ no engines needed        │
└─────┬──────────┘          └──────────┬───────────┘          └──────────────────┘
      │                                 │
      └────────────────┬────────────────┘
                        │
                ┌───────▼────────┐
                │  NUMBER GUARD    │  ← Rust/Python validator: every number NxanceLM
                │  (SUB-24 / M-11) │    says must exist in an engine's output object
                └───────┬────────┘
                        │
                ┌───────▼─────────┐
                │  NXANCE LM        │  ← 18 mini-engines. Only place an external/
                │  (chat + narrate) │    fine-tuned LLM is called. Everything else
                └──────────────────┘    here (retrieval, routing, memory) is Python.
```

Everything above the Number Guard box is **pure computation, no AI, no external API cost**. The LLM only ever sits at the very last step, turning already-computed numbers into sentences (English/Hindi/Hinglish).

---

## 2. Tech stack — what to actually use, and why

| Layer | Technology | Why |
|---|---|---|
| Core engines (HC, Construction, quant math) | **Python** (`numpy`, `pandas`, `scipy`, `PyPortfolioOpt`) | Every formula in this doc is standard, textbook quant finance — these libraries implement MVO, Black-Litterman, Sharpe/Sortino, correlation, etc. out of the box. No need to write linear algebra by hand. |
| Number Guard + any latency-critical calc | **Rust** (once we're past MVP) | Number Guard runs on *every* AI response — it needs to be fast and airtight. Python is fine for MVP; move to Rust when latency or scale demands it. |
| API layer | **FastAPI** (Python) | Matches the existing skeleton, async-friendly, auto-generates OpenAPI docs, fast to iterate. |
| Database | **Postgres** (via Supabase to start) | Relational data (users, portfolios, holdings, reports) fits relational. Supabase gives us auth + Postgres + storage in one place for MVP speed. |
| Time-series price data | **TimescaleDB extension on Postgres** (later) or plain Postgres tables (MVP) | Price history is time-series by nature; Timescale is a drop-in Postgres extension, no new infra needed until we actually need the performance. |
| Caching | **Redis** | Nightly-precomputed scores, market snapshots, and any repeated engine output get cached so the app hits sub-10-second response times without recomputing. |
| Scheduled jobs | **cron** (MVP) → **Airflow/Prefect** (scale) | Nightly data pulls + universe scoring. Start simple. |
| Retrieval / RAG for NxanceLM | **pgvector** (Postgres extension) or **Qdrant** | Stores embeddings of SEBI circulars, AMFI data, news, so the LLM can look things up instead of guessing. |
| Frontend | **React / TypeScript** (already prototyped) | Matches existing 30-screen prototype and the liquid-glass design system already built. |
| Hosting | **Railway** (MVP) → dedicated infra later | Matches current stack decision; cheap, fast to deploy, upgrade path exists. |
| Payments | **Razorpay** | Already the decided gateway (KYC submission is the current launch gate). |
| LLM (chat layer only) | **Claude/GPT API to start; open-source 7B–8B fine-tune (Llama/Mistral/Qwen-class) once volume justifies self-hosting** | Cheapest path to a working chat experience now; self-hosting removes per-token cost once usage is high enough to justify a GPU box. |

**Deliberately not used at MVP:** quantum computing (QAOA/cloud QPU), a trillion-parameter model, GPU training clusters. These stay on the long-term roadmap (Phase 1+/Final Phase) as separately funded R&D tracks — they are not on the critical path to a working product.

---

## 3. The quant math — mapped from the MIT Quant Bible to what we're building

Every "quant" claim in our engine docs is a known, textbook technique. None of it requires machine learning or a trained model — it requires implementing formulas correctly.

| What our docs call it | What it actually is | Reference | Python |
|---|---|---|---|
| Required XIRR / goal probability | Cash-flow IRR + future-value solving | Standard corporate finance | `scipy.optimize`, `numpy-financial` |
| Forecasting Engine ("78% chance of reaching goal") | **Monte Carlo simulation** — simulate thousands of random return paths from the portfolio's historical mean/volatility, see what % hit the target | Quant Bible §2–3 (probability, LLN/CLT) | ~30 lines of vectorized `numpy`, no ML |
| Risk Analysis Engine | Portfolio volatility, Sharpe/Sortino ratio, max drawdown, VaR/CVaR | Quant Bible §2.2–2.5 (expected value, variance, covariance) | `numpy`/`pandas` on price history |
| Correlation Engine | Correlation matrix of historical returns | Quant Bible §2.5 (covariance & correlation) | `pandas.DataFrame.corr()` — one line |
| Asset Allocation Engine — **Black-Litterman** | 1990s published formula combining market-implied returns with our view/risk tilt | Standard portfolio theory | `PyPortfolioOpt` has it built in |
| MVO Optimisation Engine | **Markowitz Mean-Variance Optimization** (1952) — the actual foundation of "modern portfolio theory" | Quant Bible §4 regression/optimization concepts underpin this | `PyPortfolioOpt`, or `cvxpy` |
| Selection Engine (16-layer FIT score) | A weighted scoring model — P/E, ROE, volatility, momentum, liquidity, each normalized 0–100 and combined | Quant Bible §4 (regression, feature engineering intuition) | Hand-written scoring function — this is feature engineering, not AI |
| Behaviour Analysis Engine | Prospect Theory-style scoring of stated vs. revealed risk tolerance from crash-reaction answers + transaction history | Quant Bible §2 (conditional probability/Bayes intuition for updating belief about the user) | Rule-based scoring, `pandas` |
| Tax-Aware Optimiser | LTCG/STCG rule lookup table applied before suggesting a sell | Rule-based, no ML | Plain conditional logic |
| Rebalancing Engine | Compare current weights to target weights, flag drift beyond a threshold | Simple diff logic | `pandas` |
| Backtesting Engine | Replay the portfolio's asset weights against real historical price data (2008, 2020 COVID, etc.) | Standard backtesting | `pandas` + historical price data |
| Regression-based signals (any "which factor matters" question) | OLS regression, ridge/lasso for multicollinearity, F-tests/t-tests for significance | Quant Bible §4.3–4.6 (regressions, dimensionality reduction, econometrics) | `scikit-learn`/`statsmodels` |

**Two things we quietly drop or downgrade for v1 (per the earlier cost conversation):**
1. **QAOA / quantum optimisation** — real quantum computers can't currently beat classical MVO/Black-Litterman at our portfolio sizes. Keep it as a Phase 1+ R&D track (simulated → cloud QPU → dedicated, per the existing roadmap), not part of the v1 build.
2. **"Trillion data points" / from-scratch trillion-parameter model** — we don't have that scale of data and don't need it. A solid, nightly-updated dataset of Indian + major global instruments (thousands of instruments, years of daily prices) is what actually powers this, and that's realistic and buildable now.

---

## 3.5. File Ingestion — how uploads actually get read (zero AI)

Health Check's flow starts with **Upload**, so this needs its own module, separate from the engines. It is entirely deterministic parsing — no AI, no LLM call, matching the "no AI below Number Guard" philosophy.

**Pipeline:** `Upload → File-type detection → Source-specific parser → Normalizer → Validated Holding objects → Health Check engines`

| Source | How it's read | Library |
|---|---|---|
| CAS (CDSL/NSDL/CAMS/KFintech PDF) | Password-unlock (PAN+DOB) → table extraction | `pikepdf`/`PyPDF2` + `pdfplumber`/`camelot` |
| Broker CSV (Zerodha, Groww, Upstox, etc.) | Column-mapped parse, per-broker template | `pandas.read_csv()` |
| Excel exports | Direct parse | `openpyxl`/`pandas` |
| Screenshot (fallback only) | OCR — the **only** AI-adjacent step in ingestion, and it's a narrow text-extraction model, not NxanceLM; output still goes through the same validation as every other source | Tesseract or a cloud OCR API |

Every source, regardless of origin, normalizes into **one canonical `Holding` schema** (ISIN, quantity, avg cost, current value, asset class, folio/account ref) before touching any engine — this is the piece that actually matters, since it means Risk/Correlation/Tax/etc. never need to know what the original file looked like.

**Validation before engines run:** cross-check every ISIN against the instrument universe table; anything unmapped or ambiguous gets flagged for user confirmation rather than silently guessed or dropped — a wrong parse is as much a trust failure as a wrong AI-generated number, so it gets the same "never guess" discipline as Number Guard.

**Repo placement:** its own top-level module, not inside `engines/` (it's user-triggered, not nightly, but is still pure plumbing):

```
nxance/
├── ingestion/            # file_detect, cas_parser, broker_parsers/, ocr_fallback, normalizer
```

**Maintenance reality:** broker CSV formats and CAS layouts change occasionally per source/RTA — budget for per-source unit tests against real (anonymized) sample statements, and a hard rule that a failed/ambiguous parse always surfaces to the user for confirmation rather than failing silently or guessing.

---

## 4. Health Check Engine — all 26 sub-engines, mapped to what builds each

Health Check flow: **Upload → Diagnose → Advise → Manage.** Already has a working skeleton for most of these (`nxance/engines/health_check/`).

| # | Sub-engine | What it does | Built with |
|---|---|---|---|
| 01 | Analysis Engine (gap-finder) | What's held vs. what's needed → every gap, with root cause | Python, rule comparison against goal profile |
| 02 | Risk Analysis Engine | Volatility, Sharpe/Sortino, VaR/CVaR, max drawdown | `numpy`/`pandas` |
| 03 | Fraud Gate | Screens holdings against SEBI enforcement + governance flags | Rule-based lookup against a maintained list |
| 04 | Behaviour Analysis Engine | Crash-reaction + check-frequency answers → risk archetype | Rule-based scoring |
| 05 | Tax Efficiency Engine | LTCG/STCG-aware nudges | Rule lookup table |
| 06 | Forecasting Engine | Goal probability via Monte Carlo | `numpy`, vectorized simulation |
| 07 | Guidance Engine (advisory core) | Turns gaps into a ranked, explained fix list | Python scoring/ranking logic |
| 08 | Selection Engine (16 layers) | Same engine Construction uses — scores replacement candidates | Weighted scoring function |
| 09 | Backtesting Engine | Replays portfolio through historical crashes | `pandas` + stored price history |
| 10 | Analysis & Managing | Ongoing watch after report is delivered | Scheduled job + diff logic |
| 11 | Rebalancing Engine | Flags drift beyond threshold | `pandas` diff |
| 12 | Redesigning Engine (SIP) | Adjusts ongoing SIP plan | Rule-based recompute |
| 13 | Peer Comparison Engine | Percentile ranking vs. anonymized user base | SQL/`pandas` groupby (needs real user data first) |
| 14 | Goal-Drift Watchdog | Detects when stated goal/timeline has changed | Scheduled diff against `QuestionnaireResponse` |
| 15 | Execution & Order Engine | The only engine that touches money — executes an approved action | Go/Python service + broker/Razorpay integration; gated behind explicit user approval |
| 16 | User Behaviour Engine | Shapes every gap/fix to who the user actually is (observed, not just stated) | Rule engine over transaction + interaction history |
| 17 | Quantum Supervisor (Q-Core) | Global optimality re-check, quantum risk re-check | **Simulated classically at MVP**; real quantum cloud access deferred to Phase 1+ |
| 18 | Own AI Engine (NxanceLM) | Checks meaning, explains every gap & fix, writes narration | LLM call, Number-Guard-checked — the *only* AI-touching sub-engine |
| 19 | Data Intelligence Engine | Nightly pre-compute of the scored instrument universe | Scheduled job, Postgres |
| 20 | Speed & Orchestration | Owns the <10s response budget — parallelizes the engine DAG | FastAPI + async orchestration, Redis cache |
| 21 | Report Card & Tracking | Generates the downloadable report | `reportlab` (PDF), already stubbed in skeleton |
| 22 | Asset Universe Engine | India + global instrument eligibility, amount-unlock logic | Postgres `Instrument` table + rule filters |
| 23 | Scenario Sandbox Engine | "What if" simulation on demand | Reruns Monte Carlo/backtest with modified inputs |
| 24 | Number Guard (Rust Verifier) | Cross-checks every ₹/%/date the AI outputs against source | Rust (or Python at MVP), the trust backbone |
| 25 | Peer Intelligence Engine | Crowd-level patterns, deferred to Phase 2 per roadmap | SQL aggregation once user base exists |
| 26 | Compliance & Audit Engine | Every user-visible number traces to an `engine_id` + version + input snapshot | Append-only `AuditLog` table (already in skeleton's `db.py`) |

---

## 5. Construction Engine — all 26 sub-engines

Construction flow: **Questionnaire → Build → Manage.** Shares Selection Engine (08/03) and most Layer-16-26 infra with Health Check — build those once, use in both.

| # | Sub-engine | What it does | Built with |
|---|---|---|---|
| 01 | Profile & Goal | Turns questionnaire answers into a structured profile | Python data capture + validation |
| 02 | Asset Allocation | **Black-Litterman** — combines market-implied returns with the user's stated view/risk tilt | `PyPortfolioOpt` |
| 03 | Selection Engine (16 layers) | Scores every candidate instrument 0–100 across 16 weighted factors | Hand-written scoring function on top of nightly-scored universe |
| 04 | Constraint + Fraud Screen | Applies exclusions (asset-class toggles, ESG, fraud list) before allocation runs | Rule-based filter |
| 05 | Correlation Engine | Correlation matrix across candidate instruments | `pandas.DataFrame.corr()` |
| 06 | MVO Optimisation | **Markowitz Mean-Variance Optimization** — the actual portfolio-weight solver | `PyPortfolioOpt` / `cvxpy` |
| 07 | QAOA Quantum Optimisation | Marketing-stage today — classical MVO produces the same practical result at our scale | Deferred to Phase 1+ (simulated) → Phase 2 (cloud QPU) |
| 08 | Backtesting Engine | Replays candidate portfolio through historical crash scenarios | `pandas` + price history |
| 09 | Risk Analysis Engine | Same risk math as Health Check's SUB-02, run on the *proposed* portfolio | `numpy`/`pandas` |
| 10 | Tax-Aware Optimiser | Adjusts allocation for tax efficiency before finalizing | Rule lookup |
| 11 | Analysis & Managing | Post-build ongoing watch | Scheduled job |
| 12 | Rebalancing Engine | Shared with Health Check's SUB-11 | `pandas` diff |
| 13 | Redesigning Engine (SIP) | Adjusts SIP schedule over time | Rule-based recompute |
| 14 | Execution & Order | Same execution engine as Health Check's SUB-15 | Go/Python + broker integration |
| 15 | Life-Event Adaptation | Detects and reacts to a stated life change (job loss, marriage, new goal) | Rule engine over profile changes |
| 16 | User Behaviour Engine | Shared with Health Check's SUB-16 | Shared module |
| 17 | Quantum Supervisor (Q-Core) | Shared with Health Check's SUB-17 | Shared, simulated at MVP |
| 18 | Own AI Engine (NxanceLM) | Explains every allocation decision, "why this fund" | LLM call, Number-Guard-checked |
| 19 | Data Intelligence Engine | Shared nightly-scored universe | Shared with Health Check |
| 20 | Speed & Orchestration | Owns <10s build time | Shared orchestration layer |
| 21 | Multi-Goal Engine | Builds/allocates across more than one simultaneous goal | Extends SUB-01/02 to a goal-weighted allocation |
| 22 | Scenario Sandbox Engine | "What if I invest ₹X more/less" simulation | Reruns MVO with modified inputs |
| 23 | Asset Universe & Eligibility | India, global, amount-unlock, suggestion priority | Shared with Health Check's SUB-22 |
| 24 | Number Guard | Shared verifier | Shared module |
| 25 | Peer Intelligence Engine | Deferred to Phase 2 | Shared with Health Check |
| 26 | Compliance & Audit Engine | Shared audit trail | Shared `AuditLog` |

**Practical note:** SUB-16 through SUB-26 in both engines are largely the *same* shared infrastructure (behaviour tracking, Q-Core, NxanceLM hook, data intelligence, orchestration, number guard, compliance) — build these once as shared modules (`engines/shared/`), not twice. The skeleton already does this correctly.

---

## 6. NxanceLM — all 18 mini-engines, and where the "trained AI" actually sits

This is the only part of the product that touches an LLM. Everything else in this document is AI-free.

| # | Mini-engine | What it does | Built with |
|---|---|---|---|
| 01 | Intent & Understanding | Figures out what the user is actually asking | Rule-based intent router for known buttons; LLM call only for free text |
| 02 | Tokenizer & Encoder | Standard NLP preprocessing | Existing tokenizer of whichever base model we use (don't build our own) |
| 03 | Knowledge & Retrieval (RAG) | Looks up SEBI circulars, AMFI data, news, our own engine outputs | `pgvector`/Qdrant + embedding model |
| 04 | Reasoning Core | The actual language model doing the "thinking" | **Existing open-source model, fine-tuned** (or commercial API to start) — not trained from scratch |
| 05 | Research & Analysis | Synthesizes retrieved data into an answer | LLM + RAG context |
| 06 | Explainability Engine | Reconstructs the "why" behind a gap or fix in plain language | LLM narration over engine output, Number-Guard-checked |
| 07 | Report Card Generator | Synthesizes a readable document from engine results | LLM narration + `reportlab` for the PDF itself |
| 08 | Economy & Market Chat | Open-ended finance/economy questions | LLM + RAG, scoped strictly to finance/economy domain |
| 09 | Behaviour Tracking | Feeds observed user behaviour back into both engines | Python logging, not AI |
| 10 | Daily Reporting | Digest generation | Templated + LLM narration |
| 11 | Number-Verification Guard | **The trust backbone** — cross-checks every ₹/%/date against source | Python/Rust validator — build this first |
| 12 | Safety & Boundary Guard | Enforces "helper, never sole decider" — no lone financial calls from the AI | Rule-based policy layer wrapping every LLM call |
| 13 | Quantum Acceleration | Speeds up search/sampling for the reasoning core | Deferred — simulated at MVP, real quantum later |
| 14 | Memory & Context | Keeps chat personal across sessions | Standard conversation state + Postgres |
| 15 | Multilingual & Hinglish | Handles Hindi/English code-mixed input | Fine-tune data should include Hinglish examples; from Beta phase per roadmap |
| 16 | Voice (ASR + TTS) | Voice input/output | Off-the-shelf ASR/TTS APIs, not custom-trained |
| 17 | Proactive Alerts & Nudges | Rebalancing/drift alerts pushed to the user | Triggered by SUB-11/14, delivered via notification service |
| 18 | Self-Evaluation & Learning | Tracks whether NxanceLM's explanations were actually helpful/accurate | Logging + periodic review, from Beta phase per roadmap |

### The "some other AI, trained on our data" decision, concretely

- **Start (MBP/Alpha):** Call an existing commercial API (Claude or GPT) for Mini-04/05/06/07/08. Zero training cost, pay only per message. This is what the skeleton's `chat/llm_narrate.py` already does.
- **Once we have real usage data (Beta+):** Fine-tune an open-source 7B–8B model (Llama-class, Mistral-class, or Qwen-class — all have permissive-enough licenses and run on a single modest GPU) on:
  - Our own engine outputs paired with good narrations (the best training data we have — it's *our* domain)
  - SEBI circulars, AMFI scheme data, RBI communications, NSE/BSE filings
  - Hinglish conversational examples for Mini-15
  - This removes per-token API cost and gives us a model that's actually good at *our* narrow domain, which a general-purpose model isn't optimized for.
- **This is exactly what "own AI" should mean at this stage** — not training a new architecture from zero, but taking a proven open model and specializing it on data nobody else has (our engine outputs + India-specific financial documents). That specialization *is* the moat, not the base model.
- **From-scratch foundation model / trillion-parameter ambition ("OhshnCUDA")** stays exactly where the existing roadmap already puts it: a separately funded R&D track for Phase 1+/Final Phase, not a dependency for anything in the next 18 months.

---

## 6.5. Making the quant more efficient — upgrades that don't break Number Guard

These are input-estimation upgrades, not new architecture. They slot into the existing `engines/shared/` modules, stay fully deterministic/explainable (Number Guard is unaffected), and either cost nothing extra in compute or add only a small, bounded amount — none of them threaten the <10-second target.

**Tier 1 — do these first, no trade-offs (cheap, fast, strictly better inputs):**

| Problem | Current | Efficient upgrade | Why it's still "efficient" |
|---|---|---|---|
| Covariance/correlation matrix | Raw sample covariance | **Ledoit-Wolf shrinkage** (`sklearn.covariance.LedoitWolf` or `PyPortfolioOpt`'s `risk_models.CovarianceShrinkage`) | One function call, same speed, far more stable with limited price history — sample covariance is notoriously noisy with only a few years of data |
| Portfolio weights (MVO/Black-Litterman) | Standard mean-variance | Same solvers, fed the **shrunk covariance** instead of raw | Zero added compute, meaningfully more robust portfolios — fixes MVO's biggest real-world weakness (error maximization) |
| Return assumptions for Monte Carlo | Normal distribution | **Student-t or bootstrapped historical returns** | Slightly more code (`numpy.random.standard_t` or resampling actual historical daily returns), same runtime class, captures fat tails/crashes realistically |
| Rebalancing trigger | Fixed % drift threshold | **Drift threshold scaled by asset volatility** (tighter band for low-vol assets, wider for high-vol) | Still a simple formula, not ML — makes the existing rule smarter |

**Tier 2 — worth adding, moderate effort, still fully explainable:**

| Problem | Upgrade | Trade-off |
|---|---|---|
| MVO's sensitivity to estimation error | **Hierarchical Risk Parity (HRP)** — clusters correlated assets, allocates within clusters (López de Prado, published, built into `PyPortfolioOpt`) — run alongside MVO/Black-Litterman, or default to it for smaller portfolios | More code, but a deterministic algorithm you can still show step-by-step — Number Guard unaffected |
| VaR/CVaR accuracy for tail risk | **GARCH-filtered volatility** (`arch` package) instead of flat historical std-dev, so risk reacts to current volatility regime | Classical econometrics, still 100% explainable ("we fit a GARCH(1,1) model to recent volatility") — not ML |
| Tax-loss harvesting | **Optimal lot selection via a greedy/DP algorithm** (which specific tax lots to sell to minimize tax, not just flag a sell) | Real engineering, but deterministic and explainable, high user value |

**Tier 3 — hold until real usage data exists (don't build blind):**
- Learned/ML-based factor weights for the 16-layer FIT score
- Bayesian behavior-tolerance models
- Regime-switching return forecasting models

These need historical *outcome* data (did the recommendation actually work) that doesn't exist pre-launch. Building them now means fitting to noise — worse than the current hand-set weights, dressed up as more sophisticated.

**The underlying principle:** improve the estimation of the *inputs* (covariance, volatility, return distribution) before touching the optimizer itself. Markowitz/Black-Litterman aren't the weak link — noisy inputs are. Shrinkage estimators and fat-tailed simulation are the highest-leverage, lowest-cost, zero-architecture-risk upgrades available, and they're invisible to the user while making every number the app shows meaningfully more trustworthy.

---

## 6.6. Plan tiering — which sub-engines are Basic vs. Growth vs. Pro

Gating happens entirely in the `api/` layer via one shared `has_feature(user, flag)` helper (per Section 10, item 6) — no engine itself needs to know which plan called it. Number Guard, Compliance & Audit, and every other trust/infra engine below are **never gated**; only decision-producing engines are.

**Never gated — runs for every user on every plan (infra/trust, not a feature):**

| # | Engine |
|---|---|
| 24 | Number Guard |
| 26 | Compliance & Audit Engine |
| 19 | Data Intelligence Engine (nightly universe scoring) |
| 20 | Speed & Orchestration |
| HC-03 / Const-04 | Fraud Gate / Constraint + Fraud Screen |
| 22/23 | Asset Universe & Eligibility |

**Basic (Starter) — the non-negotiable "construct + analyze" core:**

| # | Engine | Flow |
|---|---|---|
| Const-01 | Profile & Goal | Construction |
| Const-02 | Asset Allocation (Black-Litterman) | Construction |
| Const-03 | Selection Engine (16-layer) | Construction |
| Const-05 | Correlation Engine | Construction |
| Const-06 | MVO Optimisation | Construction |
| Const-09 | Risk Analysis (on proposed portfolio) | Construction |
| HC-01 | Analysis Engine (gap-finder) | Health Check |
| HC-02 | Risk Analysis Engine | Health Check |
| HC-07 | Guidance Engine | Health Check |

**Growth — adds depth, automation, forecasting (8 additions on top of Basic):**

| # | Engine |
|---|---|
| HC-04 / shared | Behaviour Analysis Engine |
| HC-06 | Forecasting Engine (Monte Carlo goal probability) |
| HC-05 / Const-10 | Tax Efficiency / Tax-Aware Optimiser |
| HC-11 / Const-12 | Rebalancing Engine |
| Const-14 / HC-15 | Execution & Order Engine |

**Pro — completes all 26+26, adds remaining depth + power-user features:**

| # | Engine |
|---|---|
| HC-09 / Const-08 | Backtesting Engine |
| HC-13 | Peer Comparison Engine |
| Const-22 | Scenario Sandbox Engine |
| HC-14 | Goal-Drift Watchdog |
| Const-13 / HC-12 | Redesigning Engine (SIP) |
| Const-15 | Life-Event Adaptation |
| Const-21 | Multi-Goal Engine |
| HC-13 / Const-25 | Peer Intelligence Engine (Phase 2, exclusive once live) |

**Not engines — service-level, handled outside `has_feature`:** fastest queue, priority support, early access. These are orchestration/ops-layer flags, not engine unlocks.

**NxanceLM quota — separate axis from engine gating**, since every plan needs some narration:

```python
# engines/shared/feature_gate.py

PLAN_ENGINES = {
    "one_time": {"health_check_report"},  # report unlock only, no ongoing engines

    "starter": {
        "const_profile_goal", "const_asset_allocation", "const_selection",
        "const_correlation", "const_mvo", "const_risk_analysis",
        "hc_gap_finder", "hc_risk_analysis", "hc_guidance",
    },

    "growth": {
        # everything in starter, plus:
        "hc_behaviour_analysis", "hc_forecasting_monte_carlo",
        "hc_tax_efficiency", "const_tax_optimiser",
        "hc_rebalancing", "const_rebalancing",
        "const_execution_order", "hc_execution_order",
    },

    "pro": {
        # everything in growth, plus:
        "hc_backtesting", "const_backtesting",
        "hc_peer_comparison", "const_scenario_sandbox",
        "hc_goal_drift_watchdog", "const_redesigning_sip", "hc_redesigning_sip",
        "const_life_event_adaptation", "const_multi_goal",
        "hc_peer_intelligence", "const_peer_intelligence",
    },
}

NXANCE_LM_DAILY_QUOTA = {
    "one_time": 0,
    "starter": 20,
    "growth": 100,
    "pro": 500,   # rename away from "unlimited" until self-hosted fine-tuned model is live
}

def has_feature(user, engine_flag: str) -> bool:
    plan = user.active_plan
    allowed = PLAN_ENGINES.get(plan, set())
    # growth/pro should inherit lower tiers rather than duplicating sets by hand in prod;
    # shown flat above for clarity — build as a tier-inheritance chain in code.
    return engine_flag in allowed
```

Every API route checks `has_feature()` before invoking an engine; Speed & Orchestration's DAG should only include engines the user's plan allows, so ungated compute is never spent on a request that can't use the result.

---

## 7. Data layer & the <10-second performance target

The product's core promise — a real-time health score or a built portfolio in under 10 seconds — is a **caching and orchestration problem**, not an AI problem.

- **Nightly batch job** (`data_pipeline/`): pulls prices (NSE/BSE, AMFI NAVs, or `yfinance`/a paid Indian data API), pulls news, and pre-computes the 16-layer FIT score for every instrument in the universe. This is the expensive part, and it runs once a day, off the user-facing request path.
- **At request time**, the engines read from this pre-scored universe (Postgres, hot data in Redis) — they are not recomputing scores for 5,000 instruments live. This is what makes sub-10-second response times realistic without quantum hardware.
- **Parallel engine DAG:** independent sub-engines (Risk, Correlation, Tax, Behaviour) run concurrently, not sequentially, with Speed & Orchestration (SUB-20) owning the deadline budget and defined fallback behavior if any one sub-engine is slow.
- **Number Guard runs after** all engine output is assembled and after the LLM narrates — it's a final validation pass, not a bottleneck in the middle.

---

## 8. Frontend — matches what's already built

The existing 30-screen prototype (liquid-glass, deep purple-navy, glassmorphism, cyan/blue accents, Plus Jakarta Sans) is the frontend target. Key points from the backend spec and terminal mockup:

- **NxanceLM Terminal** has a left sidebar of category tabs (Market, News, Currency, Commodities, Equities, Macro, Technology, Startups, Trade, Research, Analysis), a persistent **"Number Guard Active | Verified Data Environment"** status header, and a bottom free-text "Ask Nxance" box — with a set of **suggested query buttons** ("How does current scenario affect my strategy?", "Make report card of my portfolio?", "Build strategy for me?", "What's going on in the market today?") that run as **zero-AI-cost intent-routed templates**, not LLM calls. Free-text is the only path that costs LLM money.
- **Terminal tab itself needs zero AI** — it's a data-plumbing + UI problem: market data API → format → render, same pattern as Moneycontrol/Screener. Asset detail pages, news feed, "how this news affects your holding" (ticker/sector string-matching) are all rule-based.
- Every screen that shows a specific number (Sharpe ratio, health score, probability %, SIP amount, correlation, beta) must trace to a named field in an engine's output object — this is the same Number Guard discipline extended to the whole UI layer, not just the chat.

---

## 9. Repo structure (already scaffolded — extend, don't rebuild)

```
nxance/
├── data_pipeline/        # nightly: fetch_prices, fetch_news, score_universe, db models
├── engines/
│   ├── health_check/     # sub01–sub14 (+16–26 shared)
│   ├── construction/     # sub01–sub15,21,22 (+16–26 shared)
│   └── shared/           # number_guard, monte_carlo, correlation, xirr — used by both engines
├── terminal/              # market_view, asset_lookup, news_view — zero AI
├── chat/                  # intent_router (free, templated) + llm_narrate (only AI-cost path) + file_generator
├── api/                   # FastAPI gateway — the one entrypoint everything sits behind
└── frontend/               # React/TS, liquid-glass design system
```

---

## 10. Suggested build order

1. **Auth + Users + Plans** — no engine dependency, pure foundation
2. **Number Guard + Retrieval/RAG pair** (SUB-24/Mini-11 and Mini-03) — build this *before* the rest of NxanceLM, per the standing founder decision, since every other AI feature depends on it existing and passing tests
3. **Wire the existing skeleton's Health Check + Construction engines** behind the API endpoints already scoped in the backend spec — this is mostly plumbing; the math is done
4. **Dashboard** (depends on #3 for portfolio valuation)
5. **Reports screen** (depends on #3, plus the two skeleton extensions already scoped: Monte Carlo distribution output, portfolio beta/overlap)
6. **Billing/paywall gating** across all of the above — one shared `has_feature(user, flag)` helper, never scattered per-endpoint
7. **Terminal** — independent, can be built in parallel with 1–6, zero AI
8. **Chat/NxanceLM** — deliberately last; the one part with a recurring cost, and it depends on everything above already working and already tested by real numbers

This order means we can demo Health Check + Construction end-to-end, with real quant math, **before a single LLM call is wired in** — which is exactly the sequencing that keeps AI cost off the critical path until we actually need it.

---

## 11. What this buys us

- A fully working, demoable core product (Health Check + Construction, both 26-engine systems) that costs **compute only** — a small VPS, no per-request AI bill.
- An AI layer that starts as a thin, cheap wrapper (commercial API) and graduates to a **self-hosted, domain-fine-tuned open model** once usage justifies the GPU cost — without ever needing to train a model from zero.
- A trust architecture (Number Guard) that's provably testable: every number in the product traces to a deterministic function with visible inputs, which is both an engineering discipline and the core of our "no black box" pitch to users and investors.
- A build sequence where quantum computing and a from-scratch trillion-parameter model stay exactly where they belong: funded, later-phase R&D bets — not blockers to shipping.

---

## 12. Auth & security

- **Auth:** Supabase Auth to start (matches Section 2's DB choice) — email/OTP + optional social login. JWT session tokens validated at the FastAPI gateway before any engine call.
- **Sensitive data at rest:** portfolio holdings, PAN, financial goal data — encrypted at rest (Postgres column-level encryption or Supabase's built-in encryption), never logged in plaintext anywhere, including error logs.
- **In transit:** TLS everywhere, no exceptions, including internal service-to-service calls once infra grows past a single Railway deployment.
- **CAS/broker file handling:** uploaded files (which may contain PAN, DOB used as CAS password) are processed and then either deleted or encrypted at rest — decide retention policy explicitly, don't default to "keep forever."
- **Execution & Order Engine (HC-15/Const-14):** the only engine that touches real money — needs its own stricter auth check (re-confirmation/step-up auth before executing) separate from normal session auth, regardless of plan tier.

---

## 13. Compliance & regulatory (India-specific — treat as a launch blocker, not a later phase)

This is a real business-risk gap, not a code gap, and needs a lawyer/compliance consultant alongside engineering:

- **SEBI RIA (Registered Investment Advisor) registration** — if the product gives personalized investment advice (which Health Check's Guidance Engine and Construction's Asset Allocation explicitly do), this likely triggers RIA registration requirements under SEBI (Investment Advisers) Regulations. Confirm scope with a compliance advisor before launch, not after.
- **Advice vs. execution distinction** — SEBI treats "advising" and "executing trades" differently, with different licensing. Execution & Order Engine (SUB-15/14) sits right on this line — needs explicit legal review of whether it requires a separate broker/execution license or a partnership with a licensed broker instead of built in-house.
- **Data privacy** — DPDP Act (India's data protection law) applies to PAN, financial holdings, and behavioral data collected. Consent flows, data retention limits, and right-to-deletion need to be designed in from the start, not bolted on.
- **Fraud Gate's SEBI enforcement list** — needs a defined, auditable process for how that list is sourced and kept current, since it's a safety-critical rule-based screen.

**Action item:** this section is a placeholder for a real compliance audit, not a substitute for one — this should run as a parallel workstream alongside engineering, ideally starting now given typical registration timelines.

---

## 14. Error handling & fallback behavior

- **Engine-level failure:** if any sub-engine in the DAG (Speed & Orchestration, SUB-20) fails or times out, the request should degrade gracefully — return partial results with a clear "X couldn't be computed" flag, never a silent wrong number. This is Number Guard's philosophy extended to failure states, not just AI output.
- **LLM/API downtime:** if the commercial LLM API (or later, the self-hosted model) is unreachable, NxanceLM should fail to a templated "we couldn't generate an explanation right now, here are the raw numbers" response — the deterministic engines' output should never be blocked by an LLM outage, since 90% of the product doesn't need AI to function (Section 0).
- **Ingestion failure:** a broker format change or unparseable file should never silently drop or misread a holding — always surface to the user for manual confirmation (Section 3.5).
- **Retry/backoff policy:** needed for all external calls (broker APIs, Razorpay, market data feeds, LLM API) — not yet specified, should be standardized once in a shared `api/` utility rather than per-integration.

---

## 15. Testing strategy

- **Quant engine correctness:** backtest each engine's output against known benchmarks (e.g., MVO weights against a reference implementation, Monte Carlo probability against an analytically solvable simplified case) — this is how you catch a formula bug before a user sees a wrong number.
- **Number Guard itself:** needs adversarial testing — deliberately feed it AI outputs containing invented/wrong numbers and confirm it always rejects them; this is the single most safety-critical piece of code in the product and deserves the most thorough test coverage.
- **Ingestion parsers:** unit tests against real (anonymized) sample CAS/broker files per source, re-run whenever a broker changes their export format.
- **Plan gating (`has_feature`):** test that every engine correctly refuses/allows access per tier, and that Speed & Orchestration never invokes a gated engine for a user whose plan excludes it (wasted compute otherwise).

---

## 16. Onboarding / questionnaire flow

Construction's Profile & Goal engine (Const-01) and Health Check's Behaviour Analysis depend on a structured questionnaire whose actual content isn't specified yet. Needs a defined set of questions covering, at minimum:
- Financial goals (amount, timeline, priority if multiple)
- Risk tolerance (stated) — crash-reaction scenario questions, per Section 5's Behaviour Analysis Engine
- Current financial situation (income, existing investments, liabilities)
- Constraints (ESG preferences, asset-class exclusions, liquidity needs)

This should be designed once, likely alongside product/design (matches the existing 30-screen prototype's onboarding flow), and treated as a first-class deliverable — the entire Construction engine's output quality depends on what this questionnaire actually asks.

---

## 17. Data source contracts

Section 2 lists NSE/BSE, AMFI, RBI, and news feeds as the data layer's inputs, but the actual sourcing method has cost and legal implications that need pinning down:
- **NSE/BSE price data:** official paid API/data vendor (e.g., a licensed market data provider) vs. `yfinance`-style free sources — free sources often have licensing restrictions on commercial redistribution, worth confirming before relying on them at scale.
- **AMFI NAV data:** publicly available, lower risk, but confirm update frequency matches the nightly batch job's needs.
- **News feeds:** needs a defined, budgeted source (news API subscription) rather than ad-hoc scraping, both for reliability and to avoid ToS issues.
- **RBI communications:** public, but needs a defined ingestion cadence for NxanceLM's RAG layer to stay current.

---

## 18. Monetization mechanics beyond the 4 tiers

The pricing tiers (Section 6.6) define *what* each plan includes; these are the *mechanics* that still need defining:
- **Upgrades/downgrades mid-cycle:** proration logic with Razorpay — does upgrading mid-month prorate the difference, or start a fresh cycle?
- **Cancellation:** what happens to a user's existing portfolios, reports, and data access when they cancel or downgrade — do they lose access to Growth/Pro-only engine outputs immediately, or retain read-only access to already-generated reports?
- **One-time unlock → subscription conversion:** the ₹99 one-time plan is explicitly "not a plan" per the pricing image — needs a defined upsell path (e.g., a time-limited discount prompt) into Starter/Growth, since it's a funnel qualifier (MBP success-gate) rather than a standalone product.
- **Failed payments/dunning:** Razorpay webhook handling for failed renewals — grace period before downgrading access, and what the user sees during that window.

---

## 19. KYC flow

Section 2 already flags KYC submission as the current launch gate, so this needs its own concrete flow, not just a mention:

- **What's collected:** PAN, Aadhaar (via DigiLocker or manual upload), bank account for payouts/SIP debits, signature — standard for any SEBI-adjacent financial product in India.
- **Verification method:** DigiLocker integration is the cleanest path for Aadhaar/PAN pull with consent, versus manual document upload + third-party KYC verification API (e.g., Karza, Signzy, or similar KYC-as-a-service providers common in Indian fintech).
- **Where it sits relative to the product:** likely gates Construction's Execution & Order Engine specifically (can view/build a portfolio pre-KYC, can't actually execute trades until KYC clears) rather than blocking the whole product — worth deciding explicitly so Basic-tier users aren't blocked from diagnosis/analysis while KYC is pending.
- **Re-KYC / periodic refresh:** SEBI/RBI periodically require re-verification (e.g., address/PAN re-confirmation) — needs a scheduled reminder flow, not a one-time gate.
- **Storage:** KYC documents are highly sensitive — same encryption-at-rest discipline as Section 12, with even stricter access logging (who viewed a user's PAN/Aadhaar, when).

---

## 20. Customer support / helpdesk

- **In-app support channel:** a way for users to ask a human (not NxanceLM) a question — chat widget, ticket system, or WhatsApp Business integration (common in Indian consumer fintech).
- **Number disputes:** given the whole product's pitch is "every number traces to source" (Number Guard), there needs to be a defined path for a user to say "this number looks wrong" and get it investigated against the Audit Log (Section 4/5, SUB-26) — this is a natural, high-trust support flow uniquely enabled by your own architecture.
- **Escalation tiers:** matches your plan tiers naturally — e.g., Starter gets standard-queue support, Growth/Pro get "priority support" (already promised in the pricing image, Section 6.6) — needs a real ticketing priority mechanism, not just a marketing label.
- **Tooling:** a lightweight helpdesk (Freshdesk, Zendesk, or a simple in-house ticket table in Postgres for MVP) rather than building this from scratch initially.

---

## 21. Admin / internal ops panel

Needed by your own team, not end users — for running the business day to day:

- **Engine health dashboard:** which sub-engines are failing/slow/timing out in production (feeds off the same fallback/error signals from Section 14).
- **Flagged-parse review queue:** ingestion failures or ambiguous holdings (Section 3.5) that got surfaced to a user for confirmation should also be visible to your ops team, to catch systemic parser breakage early (e.g., a broker changed their CSV format for everyone, not just one user).
- **Fraud Gate list management:** an interface to update the SEBI enforcement/governance flag list (Section 4, HC-03) rather than editing it via direct DB access.
- **Business metrics view:** plan distribution, conversion between tiers, churn, NxanceLM usage/cost per plan (ties directly into the quota table in Section 6.6) — this is what tells you if your pricing/cost math is actually working in production.
- **User support lookup:** for the support flow in Section 20 — an internal view of a user's Audit Log entries to investigate a disputed number quickly.

---

## 22. Notifications infrastructure

Mini-17 (Proactive Alerts & Nudges) is listed as an engine that triggers alerts, but delivery itself is separate infrastructure:

- **Channels:** push notification (mobile), email, SMS, and/or WhatsApp Business API — WhatsApp is worth strong consideration given its dominance for transactional/financial alerts in the Indian market.
- **Trigger sources:** Rebalancing Engine drift alerts, Goal-Drift Watchdog (HC-14), SIP due reminders (Redesigning Engine), KYC re-verification reminders (Section 19) — all route through one shared notification service rather than each engine implementing its own delivery.
- **User preferences:** users should control channel/frequency per alert type — needs a preferences table, not a single global on/off switch.
- **Plan-tier relevance:** some proactive alerts (e.g., Goal-Drift Watchdog) are Pro-tier per Section 6.6 — the notification service should respect the same `has_feature` gating as everything else, so a Starter user doesn't receive alerts from an engine their plan doesn't include.

---

## 23. Referral / growth mechanics

Not discussed anywhere yet — needed if organic/paid acquisition alone won't hit growth targets:

- **Referral codes:** unique per-user code, tracked via a simple Postgres table (referrer, referee, status, reward).
- **Reward structure:** e.g., free month, plan credit, or unlocking the ₹99 one-time report at no cost for both referrer and referee — ties into the monetization mechanics in Section 18.
- **Attribution:** needs to be decided whether this is self-built (simple, sufficient for MVP) or via a third-party referral platform — self-built is likely fine given the low complexity of the reward logic described here.

---

## 24. Analytics / BI for the business

Distinct from the user-facing Peer Comparison/Peer Intelligence engines (Sections 4–5) — this is data *about* the business, for internal decision-making:

- **Funnel metrics:** signup → KYC completion → first portfolio built/Health Check run → paid conversion — critical given the ₹99 one-time unlock is explicitly a funnel qualifier (Section 18).
- **Engine usage stats:** which sub-engines get used most/least per tier — informs whether the Section 6.6 tier boundaries are actually right, or need rebalancing after launch.
- **NxanceLM cost tracking:** actual per-user LLM spend vs. the quota table in Section 6.6 — this is what tells you when self-hosting the fine-tuned model (Section 6) becomes worth it.
- **Tooling:** a BI layer (Metabase or a similar self-hosted tool works well against Postgres directly) rather than building custom dashboards from scratch at MVP stage.

---

## 25. Mobile app

Section 2/8 specify React/TypeScript for the web frontend, matching the existing 30-screen prototype — mobile-specific decisions are still open:

- **Web-first, PWA, or native:** if a dedicated mobile app is planned (common expectation for a personal-finance product in India), decide between a React Native shared-codebase approach (leverages existing React/TS frontend work) versus a fully native build — this is a significant scope decision that should be made explicitly, not defaulted into.
- **Push notification dependency:** native mobile push (Section 22) generally requires a native or React Native shell even if most of the UI is web-based.
- **Feature parity:** decide whether the mobile experience launches with full engine/plan parity to web, or a reduced initial feature set (e.g., Health Check + Dashboard only, Construction/Terminal later).

---

## 26. Localization beyond Hinglish

Mini-15 (Section 6) covers Hindi/English code-mixed chat for NxanceLM specifically — full UI localization is a separate, broader question:

- **Scope decision:** is the goal Hinglish chat support only (as currently scoped), or full UI translation into major Indian languages (Hindi, Tamil, Telugu, Marathi, etc.) for screens, reports, and onboarding?
- **If full UI localization is in scope:** this affects the frontend (Section 8) directly — needs an i18n framework (e.g., `react-i18next`) built into the React/TS frontend from early on, since retrofitting localization after screens are built is significantly more expensive than designing for it upfront.
- **Report generation:** the Report Card Generator (Mini-07) uses `reportlab` for PDF output — if reports need to be multilingual, font/script support for Indian languages needs to be confirmed in the PDF generation pipeline specifically, since this is a common technical gap in PDF libraries.
