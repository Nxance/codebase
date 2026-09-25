# India investment report sources → canonical schema

All ingest paths (CSV, CAS PDF, OCR, broker export, AA later) must emit **`india_portfolio_v1`**.

| Source | Typical file | Key fields | Channel enum |
|--------|--------------|------------|--------------|
| **CDSL CAS** | PDF password PAN | ISIN, qty, value, demat | `cas_cdsl` |
| **NSDL CAS** | PDF | ISIN, qty, cost, value | `cas_nsdl` |
| **CAMS MF CAS** | PDF / email | Folio, scheme, units, NAV, cost | `cas_cams` |
| **KFintech MF CAS** | PDF | Folio, scheme, units, NAV | `cas_kfin` |
| **Zerodha Console** | CSV tradebook / holdings | symbol, qty, avg, LTP | `broker_zerodha` |
| **Groww** | CSV / screenshot | MF + stocks | `broker_groww` |
| **Upstox / Angel** | CSV | holdings | `broker_*` |
| **Bank FD advice** | PDF / image | principal, rate, maturity | OCR / manual |
| **PPF passbook** | PDF / image | balance, FY credits | OCR |
| **NPS Tier-I** | statement | units NAV by scheme | OCR / CSV |
| **SGB** | demat holding | grams / units | CAS |
| **Account Aggregator** | FI data JSON | multi-FIU | `account_aggregator` (later) |

## Parser contract

```
raw bytes + source.channel
  → extractor (pdf/csv/ocr)
  → field map + confidence
  → validate against india_portfolio_v1
  → user confirm low-confidence fields
  → engines only see canonical lots
```

## Training implication

Synthetic generator produces the **same** `india_portfolio_v1` JSON so models trained offline match production ingest.
