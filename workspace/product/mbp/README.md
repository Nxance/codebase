# Nxance MBP v2 — Product-grade Minimum Buyable Product

Rebuilt for **how good products ship**, not as a form dump of the internal docs.

## Product principles (v2 + intelligence rethink)

1. **Value before account** — one-click live demo; no signup wall  
2. **Sell the insight** — hero metric is avoidable ₹/year, not a spreadsheet  
3. **Layered intelligence** — L1 quant measures → L2 ML scores → L3 embeddings → L4 optimises → L5 language explains  
4. **AI is not the calculator** — LLMs never invent ₹; Number Guard enforces  
5. **Suggestion only** — no fake execution  
6. **Buyable MBP** — free teaser + ₹99 unlock  

Architecture: `../../docs/03-technical/intelligence-architecture-rethink.md`  
Code: `app/intelligence/{quant,ml,dl,optimize,nlp,pipeline}/`

## Investor path (60 seconds)

1. Open app → **See it on a real-style portfolio**  
2. Watch five engines run  
3. Land on score + **₹ avoidable / year** + free top issue  
4. Unlock with `DEMO-UNLOCK` for full ranked fixes  

## Run

```bash
# from repo root:
cd product/mbp
./run.sh
# http://127.0.0.1:8000
```

## Stack (still ₹0)

FastAPI · SQLite · pure-Python XIRR · free AMFI · template NxanceLM + Number Guard · premium single-page UI  

## Key APIs

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/demo/run` | Instant investor demo (no auth) |
| POST | `/api/health-check` | Guest-friendly diagnosis |
| POST | `/api/construction` | Goal → plan |
| POST | `/api/unlock` | Code unlock |
| POST | `/api/chat` | Grounded Q&A |

## Codes

`DEMO-UNLOCK` · `NXANCE-TEST` · `NXANCE-PAID` (after real UPI)

## Not this release

Razorpay live, OTP auth, own LLM training, CAS OCR, AA, quantum, B2B — after paid users exist.

