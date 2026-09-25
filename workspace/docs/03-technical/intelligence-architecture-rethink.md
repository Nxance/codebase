# Nxance Intelligence Architecture — Rethink (Source of Truth)

**Status:** Active design · supersedes “AI-first / own-LLM-first / quantum-in-MBP” framing in older docs  
**Date:** 2026-07  
**Principle:** Language models do not calculate. Models predict. Optimisers allocate. Maths measures.

---

## 1. Why the old approach was wrong

Older folder docs treat **NxanceLM / hybrid Transformer / QAOA** as the centre of gravity. That is a product and research fantasy for a pre-seed MBP.

| Claim in old docs | Reality for portfolio intelligence |
|-------------------|-------------------------------------|
| Own LLM from day 1 is the moat | Moat is **correct diagnosis + ranked ₹ impact**, not Hinglish |
| TinyLlama / GPT computes insights | LLMs **hallucinate** finance numbers unless fully constrained |
| Quantum optimisers in early phases | Classical convex optimisers are enough until 10k+ users |
| One “AI engine” does everything | Finance needs **layered** systems with different failure modes |
| More sub-engines = more product | Wrong formula quietly is worse than fewer correct ones |

**Nxance is not an AI chatbot with charts.**  
It is a **measurement + prediction + optimisation + explanation** system.

---

## 2. The four layers (and a fifth for language)

```
┌─────────────────────────────────────────────────────────────┐
│  L5  LANGUAGE (NxanceLM)                                    │
│      Explain · route · summarise · never invent numbers     │
├─────────────────────────────────────────────────────────────┤
│  L4  DECISION / OPTIMISATION                                │
│      Allocation · instrument pick · constraints · rebalance │
├─────────────────────────────────────────────────────────────┤
│  L3  DEEP LEARNING (when data justifies it)                 │
│      Embeddings · sequence models · similarity              │
├─────────────────────────────────────────────────────────────┤
│  L2  MACHINE LEARNING (tabular / probabilistic)             │
│      Scores · classifiers · expected return models          │
├─────────────────────────────────────────────────────────────┤
│  L1  QUANT / DETERMINISTIC                                  │
│      XIRR · TER · HHI · correlation · risk metrics · FV     │
└─────────────────────────────────────────────────────────────┘
                         ▲
                         │ verified numbers only flow UP
```

### Ownership rule (non-negotiable)

| Output type | Owner layer | Must NOT come from |
|-------------|-------------|--------------------|
| Past returns, XIRR, TER ₹, overlap %, HHI | **L1 Quant** | LLM, neural net |
| “Will this fund keep outperforming?” | **L2 ML** (later L3) | LLM narrative |
| “Which funds are similar?” | **L3 embeddings** or L1 Jaccard | LLM guess |
| Optimal weights given goals/constraints | **L4 Optimiser** | LLM, raw chat |
| Plain-language explanation | **L5 Language** | Any layer inventing ₹ |

**Number Guard** sits between L5 and everything below: every digit in text ⊆ engine payload.

---

## 3. What each layer is for (how / when / where)

### L1 — Quant (always on · MBP day 1)

**What:** Closed-form and numerical methods with known properties.  
**When:** Every Health Check and Construction run.  
**Where:** `app/intelligence/quant/`

| Job | Algorithm family | Notes |
|-----|------------------|-------|
| True time-weighted return | XIRR (Brent root of NPV=0) | Not CAGR if cashflows irregular |
| Absolute return | (V−I)/I | Always show ₹ and % |
| Cost leak | Regular TER − Direct TER × AUM | Deterministic |
| Overlap | Jaccard / weighted holdings intersection | Holdings-based, not name fuzzy only |
| Concentration | HHI = Σ wᵢ² | Classic |
| Goal required return | Solve FV(SIP, r, n) = target | Bisection |
| Risk capacity | Weighted questionnaire score | Transparent rules |
| Stress / projection range | Historical bootstrap or simple Monte Carlo | Not a neural forecast |
| Risk stats | Vol, max DD, Sharpe-like, CVaR (when series exist) | Need price history |

**Do not replace L1 with ML.** Training a model to “predict XIRR” when you can compute XIRR is malpractice.

---

### L2 — Machine Learning (tabular · ship early but honest)

**What:** Supervised / unsupervised models on **features**, not free text.  
**When:** Scoring, ranking, anomaly flags, regime tags — after L1 features exist.  
**Where:** `app/intelligence/ml/`

| Job | Preferred approach | Why not DL first |
|-----|--------------------|------------------|
| Fund quality / FIT score | Gradient boosting (LightGBM/XGBoost) or strong linear baseline | Tabular finance: trees beat deep nets with small data |
| Risk-of-underperformance | Classifier on trailing metrics + TER + category | Interpretable features |
| Anomaly / fraud soft signals | Isolation Forest / robust z-scores | Unsupervised, no labels needed at start |
| Goal success probability | Calibrated logistic or survival-style model | Better than single FV point |
| User segment / behaviour later | Clustering on actions | After product has usage data |

**MBP stance:** Ship **feature-based scoring with explicit weights** that is *API-compatible* with a trained booster. Same interface: `predict(features) → score, confidence, drivers`. Swap rules → LightGBM without rewriting the product.

**Training data (when ready):** AMFI category returns, rolling sharpe, drawdowns, AUM, TER, manager tenure — **not** scraped tweets.

---

### L3 — Deep Learning (only when data volume + task fit)

**What:** Representation learning and sequences.  
**When:** After you have consistent history (thousands of series, nightly jobs). **Not** for first paid unlock.  
**Where:** `app/intelligence/dl/`

| Job | Model family | When justified |
|-----|--------------|----------------|
| Fund / stock embeddings | Dual encoder / metric learning | Overlap beyond top-30 holdings; “similar funds” |
| NAV / return sequence features | Temporal CNN, small Transformer, or N-BEATS-class | Forecasting *features* for L2, not user-facing magic numbers |
| Document / CAS field extraction | LayoutLM / small VLM later | Messy PDFs — after CSV/CAS parse baseline works |

**Hard rules for DL at Nxance:**

1. DL outputs are **inputs to L2/L4**, never raw “you will earn 18%” to the user.  
2. Always keep a **classical baseline**; promote DL only if offline eval beats baseline.  
3. No “train 7B from scratch” until revenue and data ops exist.

---

### L4 — Optimisation / decision (Construction heart)

**What:** Constrained allocation under goals and risk.  
**When:** Every Construction run; rebalance suggestions later.  
**Where:** `app/intelligence/optimize/`

| Stage | Method | MBP | Later |
|-------|--------|-----|-------|
| Strategic allocation | Rule + risk capacity + horizon | ✓ | Black–Litterman views |
| Weights within equity/debt | Risk parity or mean–variance (Markowitz) with caps | ✓ simplified | Full covariance from live series |
| Instrument selection | Multi-objective score (L1+L2) + constraints | ✓ | Cardinality-constrained QP |
| Tax-aware / transaction cost | Penalty terms in objective | later | |
| Quantum QAOA | Research | **out** until classical limits proven | |

**Construction is not “AI picks funds.”**  
It is **optimise → then L5 explains why**.

---

### L5 — Language (NxanceLM)

**What:** Intent routing + templated or small-LM narration.  
**When:** After L1–L4 payload is frozen.  
**Where:** `app/intelligence/nlp/`

Allowed:

- Explain score, issues, allocation in plain language  
- Route “build me a portfolio” → Construction pipeline  
- Refuse execution / stock tips as decisions  

Forbidden:

- Computing or estimating any ₹ / % not in the payload  
- Softening fraud flags  
- Replacing L4 with “I recommend 70% midcaps because…”

Templates first. Hosted small model second. Own trained finance LM last.

---

## 4. End-to-end pipelines (when what runs)

### Health Check pipeline

```
Input holdings + questionnaire
    → L1 parse & validate
    → L1 returns / cost / overlap / concentration / goal gap
    → L2 fund quality & anomaly scores (optional enhance ranking)
    → L3 embeddings (optional: better overlap / peers) 
    → L1 fraud hard rules + L2 soft anomaly
    → L4? (only for “suggested fix portfolio” slice, not required)
    → Assemble verified payload
    → L5 explain + Number Guard
    → Teaser / paywall story
```

### Construction pipeline

```
Questionnaire
    → L1 required return & risk capacity
    → L4 strategic allocation
    → L2/L1 score universe instruments
    → L3 similarity filter (optional diversity)
    → L4 weight optimiser under constraints
    → L1 fraud gate on names
    → L1 projection range (MC / closed form)
    → L5 explain + Number Guard
```

---

## 5. Prediction modelling — explicit choices

We separate **three prediction problems** that docs often blur:

| Problem | Question | Model class | User-facing form |
|---------|----------|-------------|------------------|
| **P1 Measurement** | What *did* it return? | L1 only | XIRR, ₹ gain |
| **P2 Expectation** | What *might* it return? | L2 (category prior + shrinkage) → later L3 features | Range + confidence, never single false precision |
| **P3 Goal probability** | Chance of hitting target? | L1 FV + L2 calibrated success model | Probability band + required SIP |

**Shrinkage expected returns (MBP-ready):**  
`E[r] = w · fund_history + (1−w) · category_mean` with w small when history short.  
This is better than raw trailing 3y CAGR and better than an untrained neural net.

**Monte Carlo:** geometric Brownian or bootstrap of historical residuals for **range**, not a sales graph of the median only.

---

## 6. What to change vs old docs / old MBP

| Area | Change |
|------|--------|
| Centre of product | From “own AI” → **verified quant + ranked economics** |
| Sub-engine counting | Stop worshipping 26/26/18; use **layers + jobs** |
| FIT score | From ad-hoc constants → **feature vector + scorer interface** |
| Allocation | From pure heuristics → **optimiser with constraints** |
| Overlap | Keep Jaccard; add **embedding similarity** path later |
| NxanceLM | Explicit L5 only; templates default |
| Quantum / MoE 40B | Parked behind revenue + data milestones |
| Training | Prefer **tabular ML** before any LLM fine-tune |

---

## 7. Code layout (implemented)

```
product/mbp/app/intelligence/
  quant/          # L1
  ml/             # L2
  dl/             # L3 (interfaces + safe fallbacks)
  optimize/       # L4
  nlp/            # L5
  pipeline/       # orchestration + contracts
```

Legacy `app/engines/` remains as thin wrappers calling the pipeline so the API stays stable.

---

## 8. Evaluation gates (what “better” means)

Before promoting any ML/DL model to production:

1. **Offline:** beats L1-only or rule baseline on hold-out (AUC / RMSE / rank IC).  
2. **Calibration:** predicted goal hit rates match realised buckets.  
3. **Stability:** small input noise doesn’t flip allocation wildly.  
4. **Safety:** no path where L5 can surface unguarded numbers.  
5. **Cost:** inference latency p95 &lt; product budget (MBP: few seconds total).

---

## 9. Phased capability (honest)

| Phase | L1 | L2 | L3 | L4 | L5 |
|-------|----|----|----|----|-----|
| **Now (MBP)** | Full core | Feature scorer (rules → model-ready) | Interface + fallback | Constrained heuristic + MV-lite | Templates + guard |
| **Beta** | Price series risk | Trained LightGBM FIT + anomaly | Fund embeddings v1 | Mean–variance + BL-lite | Small hosted LM optional |
| **Scale** | Full risk library | Recalibrated production models | Sequence models if they win evals | Tax-aware, multi-goal | Domain LM if economics work |

---

## 10. One sentence for the team

**Measure with maths, score with ML, represent with DL only when earned, allocate with optimisers, speak with language models — and never reverse that order.**
