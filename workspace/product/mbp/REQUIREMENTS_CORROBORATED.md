# Nxance MBP — Corroborated Requirements (Zero-Spend Build)

Source of truth: `Nxance_MBP_Master_Specification_v3`, `Nxance_Complete_MBP_Build_Guide`,
4-phase roadmap, Technology Complete Guide (Without Registration / free tier).

---

## 1. What MBP is (one statement)

Three engines (Health Check, Construction, NxanceLM), **5 sub-engines each**,
suggestion-only, assets = **stocks + MF + FD**, payment-gated from Day 1.
Core job of each engine is honest; depth is deliberately limited.

**Golden rules**
- Engines compute numbers; NxanceLM only explains (never invents ₹ / % / dates).
- Questionnaire is **not** asked at onboarding — only per engine use.
- Health Check: **upload → then questionnaire → analyse**.
- Construction: **questionnaire → then design**.
- Free teaser: score + 1 insight. Paid unlock: full gaps, fixes, plan, chat, report.

---

## 2. In scope vs out of scope

| IN MBP | OUT (later) |
|--------|-------------|
| 3 engines × 5 sub-engines | Full 26/26/18 engine suite |
| Stocks, MF, FD only | ETF, bonds, crypto, REITs, commodities, currency |
| Suggestion only | Broker execution / wallet money movement |
| Excel/CSV (+ basic PDF text) | Full CAS password unlock + OCR production |
| Template + Number Guard AI | From-scratch NxanceLM training / GPU rent |
| Manual UPI unlock codes | Razorpay live (needs business KYC; optional later free test mode) |
| Soft profile (name + phone) | Paid KYC providers (Signzy etc.) |
| SQLite local | Supabase (free tier optional later) |
| Local run / free hosting later | Paid cloud, own servers |

---

## 3. Engine map (named 5 each)

### Health Check
1. **Input / Parse** — Excel/CSV/manual → clean holdings  
2. **Analysis** — XIRR, absolute return, HHI, TER leak, goal gap  
3. **Risk** — simple vol proxy, concentration, goal-risk mismatch  
4. **Fraud Gate** — whitelist / junk name / impossible returns (critical → score ≤ 40)  
5. **Guidance** — ranked fixes with ₹ impact (suggestion only)

### Construction
1. **Profile / Goal** — required return from target, SIP, years  
2. **Allocation** — equity / debt-MF / FD split from risk + horizon  
3. **Selection** — simplified FIT (cost + consistency + fraud-pass)  
4. **Fraud Gate** — shared module  
5. **Risk / Diversification** — cap single instrument, quantity / ₹ per line

### NxanceLM
1. **Intent** — route chat to HC / Construction / explain / refuse  
2. **Number Guard** — every digit in AI text must appear in engine JSON  
3. **Explainability** — plain-language issue / pick reasons  
4. **Basic Chat** — grounded on last report only (templates, no paid LLM)  
5. **Report Writer** — 3-line verified summary  

---

## 4. Zero-rupee stack (this folder)

| Need | Spec (ideal) | Zero-spend choice |
|------|----------------|-------------------|
| Frontend | Next.js | Single HTML/CSS/JS served by FastAPI |
| Backend | FastAPI | FastAPI (same) |
| Maths | scipy / pandas | scipy, pandas, numpy (free) |
| DB + Auth | Supabase OTP | SQLite + session token (local) |
| NAV data | AMFI | mfapi.in (free, no key) |
| Stocks | paid/cheap API | Curated static universe + optional free lookups |
| FD rates | table | `app/data/fd_rates.json` |
| AI | TinyLlama GPU | **Templates only** + Number Guard (₹0 inference) |
| Payments | Razorpay live | **Manual UPI + unlock code** (founder sends code after UPI) |
| Hosting | Railway + Vercel | **localhost** now; free Render/Railway later if wanted |
| Cache | Redis | In-process dict cache |

**You spend ₹0** as long as you run on your machine and use free public data.
Optional free-tier cloud accounts (GitHub, Render free) still cost ₹0 if you stay in free limits.

---

## 5. Payment without paid payment gateway

1. Free: show score + issue #1 only (paid fields stripped server-side).  
2. User pays ₹99 via your UPI (personal UPI works; no Razorpay fee stack).  
3. User messages you → you issue unlock code (or use built-in demo codes for testing).  
4. App stores unlock in SQLite → full report + chat.

Demo codes (for testing only): `DEMO-UNLOCK`, `NXANCE-TEST`.

---

## 6. Exit gates (when MBP is “done” enough to learn)

- Engine run works end-to-end in < 10s on a normal laptop  
- Excel/manual parse works on messy columns  
- Number Guard never lets a non-engine figure through  
- Fraud critical caps score  
- At least one stranger paid once (even ₹99 UPI)  

Money gates before machine gates: *“Did someone pay?”*

---

## 7. How to run (this MBP)

```bash
cd Nxance_MBP
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
# open http://127.0.0.1:8000
```
