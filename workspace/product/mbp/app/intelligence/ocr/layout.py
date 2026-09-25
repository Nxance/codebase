"""
India fintech OCR text → holdings (layout v3).

Handles messy multi-line Groww / Zerodha / MF Central / Coin style dumps
with rupee amounts, ISINs, units, and fund/stock/FD names.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any


# Non-catastrophic amount patterns. Prefer full digit runs before comma-groups
# so "Rs 100000" is not truncated to 100.
_INR_LABELED = re.compile(
    r"(?:₹|Rs\.?|INR)\s*("
    r"[0-9]{4,12}(?:\.[0-9]{1,2})?"  # plain 100000 / 108000.50
    r"|[0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?"  # 1,00,000 or 100,000
    r"|[0-9]{1,3}(?:\.[0-9]{1,2})?"  # small plain (rare)
    r")",
    re.I,
)
_INR_BARE = re.compile(
    r"(?<![A-Za-z0-9.])("
    r"[0-9]{4,12}(?:\.[0-9]{1,2})?"
    r"|[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{1,2})?"
    r")(?![A-Za-z0-9])"
)
ISIN = re.compile(r"\b(INE[A-Z0-9]{9}|INF[A-Z0-9]{9})\b")
AMFI = re.compile(r"\b(1[0-9]{5})\b")
UNITS = re.compile(r"\b([0-9]+(?:\.[0-9]+)?)\s*(?:units?|qty|quantity|shares?)\b", re.I)
DATE = re.compile(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}-\d{2}-\d{2})\b")

FUND_HINT = re.compile(
    r"\b(fund|index|flexi|bluechip|mid[\s-]?cap|small[\s-]?cap|large[\s-]?cap|"
    r"elss|nifty|sensex|liquid|gilt|hybrid|equity|debt|folio|growth|dividend|"
    r"tax\s*saver|multi[\s-]?cap|value|focused|opp(?:ortunity)?|balanced|"
    r"overnight|arbitrage|ultra[\s-]?short|corporate\s*bond|banking|psu)\b",
    re.I,
)
STOCK_HINT = re.compile(
    r"\b(ltd|limited|bank|industries|tech|motors|pharma|steel|infosys|tcs|"
    r"reliance|hdfc|icici|sbi|wipro|bharti|airtel|titan|asian\s*paints)\b",
    re.I,
)
FD_HINT = re.compile(r"\b(fd|fixed\s*deposit|deposit|rd|recurring)\b", re.I)
PLAN = re.compile(r"\b(direct|regular)\b", re.I)
AMC = re.compile(
    r"\b(axis|hdfc|icici|sbi|uti|parag\s*parikh|ppfas|mirae|nippon|kotak|"
    r"aditya\s*birla|absli|dsp|franklin|invesco|motilal|quant|bandhan|"
    r"canara|hsbc|tata|edelweiss|mahindra|navi|groww|zerodha|coin)\b",
    re.I,
)

NAME_LINE = re.compile(r"^[A-Za-z][A-Za-z0-9 &./()'%\-+]{2,80}$")
HEADER_ONLY = re.compile(
    r"^(my\s+)?(investments?|portfolio|holdings?|total|summary|overview|"
    r"current\s+value|invested|xirr|returns?|mutual\s+funds?|stocks?|"
    r"fixed\s+deposits?|assets?|home|explore|watchlist)$",
    re.I,
)
LABEL_NOISE = re.compile(
    r"\b(invested|current|value|returns?|xirr|pnl|p&l|gain|loss|day|"
    r"one\s*day|1d|1y|3y|5y|absolute|cagr)\b",
    re.I,
)


def _parse_amount(s: str) -> float | None:
    s = s.replace(",", "").strip()
    try:
        v = float(s)
    except Exception:
        return None
    return v


def _extract_amounts(ln: str) -> list[float]:
    out: list[float] = []
    seen_spans: set[tuple[int, int]] = set()
    for rx in (_INR_LABELED, _INR_BARE):
        for m in rx.finditer(ln):
            span = m.span(1)
            if span in seen_spans:
                continue
            # skip if overlaps an already-captured labeled amount
            if any(not (span[1] <= a or span[0] >= b) for a, b in seen_spans):
                continue
            raw = m.group(1)
            if not raw:
                continue
            a = _parse_amount(raw)
            if a is not None and a >= 100:  # ignore tiny / units-like
                out.append(a)
                seen_spans.add(span)
    return out


def _clean_name(n: str) -> str:
    n = LABEL_NOISE.sub(" ", n)
    n = re.sub(r"\s+", " ", n).strip(" -|•·:→>")
    n = re.sub(r"\b(direct|regular|growth|idcw|dividend)\b", " ", n, flags=re.I)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _looks_like_instrument(name: str) -> bool:
    if not name or len(name) < 3:
        return False
    if HEADER_ONLY.match(name):
        return False
    if FUND_HINT.search(name) or STOCK_HINT.search(name) or FD_HINT.search(name):
        return True
    if AMC.search(name):
        return True
    # multi-word title-ish
    words = [w for w in re.split(r"\s+", name) if w]
    if len(words) >= 2 and re.search(r"[A-Za-z]{3,}", name):
        return True
    return False


def _asset_class(name: str) -> str:
    low = name.lower()
    if FD_HINT.search(name):
        return "fd"
    if STOCK_HINT.search(name) and not FUND_HINT.search(name) and "fund" not in low:
        return "equity_stock"
    if re.search(r"elss|tax\s*saver", name, re.I):
        return "mutual_fund_elss"
    if re.search(r"debt|liquid|gilt|overnight|bond|arbitrage", name, re.I):
        return "mutual_fund_debt"
    if re.search(r"index|nifty|sensex", name, re.I):
        return "mutual_fund_index"
    if re.search(r"hybrid|balanced|multi\s*asset", name, re.I):
        return "mutual_fund_hybrid"
    return "mutual_fund_equity"


def _plan_type(text: str, name: str, asset: str) -> str:
    if "mutual" not in asset and asset != "mutual_fund_equity":
        if asset.startswith("mutual"):
            pass
        else:
            return "na"
    if "direct" in (text + " " + name).lower():
        return "direct"
    if "regular" in (text + " " + name).lower():
        return "regular"
    return "regular"


def _make_lot(
    name: str,
    amounts: list[float],
    *,
    raw_line: str,
    isin: str | None = None,
    qty: float | None = None,
    conf: float = 0.55,
) -> tuple[dict, float]:
    amounts_sorted = sorted(amounts, reverse=True)
    cur = amounts_sorted[0]
    inv = amounts_sorted[1] if len(amounts_sorted) > 1 else cur * 0.9
    # Prefer labeled order if present
    low = raw_line.lower()
    if "invested" in low and "current" in low:
        # try chronological: invested first then current in original order
        ordered = amounts
        if len(ordered) >= 2:
            inv, cur = ordered[0], ordered[1]
    if inv > cur * 3 and len(amounts_sorted) >= 2:
        inv, cur = amounts_sorted[1], amounts_sorted[0]
    asset = _asset_class(name)
    plan = _plan_type(raw_line, name, asset)
    q = qty if qty is not None else 1.0
    if conf < 0.7 and isin:
        conf = 0.8
    if conf < 0.65 and FUND_HINT.search(name):
        conf = 0.65
    return (
        {
            "lot_id": "ocr_pending",
            "asset_class": asset,
            "name": name[:80],
            "isin": isin,
            "amfi_code": None,
            "quantity": q,
            "avg_cost": round(inv / max(q, 0.001), 4),
            "invested_amount": round(inv, 2),
            "current_value": round(cur, 2),
            "plan_type": plan if asset.startswith("mutual") else "na",
            "purchase_date": "2022-01-01",
            "sector": "unknown",
            "market_cap_bucket": "multi",
            "source_row": {"raw_line": raw_line[:200]},
        },
        conf,
    )


def parse_holdings_from_ocr_text(text: str) -> dict[str, Any]:
    """
    Returns india_portfolio_v1-ish doc with lots + parse confidence.

    Multi-strategy (v3):
      A) name line + amount line (two-row mobile cards)
      B) single line name + ₹ amounts
      C) ISIN / AMFI anchored rows
      D) labeled Invested/Current pairs
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    lots: list[dict] = []
    confidences: list[float] = []

    i = 0
    while i < len(lines):
        ln = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""

        # Pure headers only — never drop amount-bearing holding rows
        if HEADER_ONLY.match(ln) or (
            re.search(r"\b(portfolio|holdings|total|summary)\b", ln, re.I)
            and not _extract_amounts(ln)
            and not FUND_HINT.search(ln)
            and not AMC.search(ln)
            and len(ln) < 40
        ):
            i += 1
            continue

        isin_m = ISIN.search(ln) or ISIN.search(nxt)
        isin = isin_m.group(1) if isin_m else None
        amounts = _extract_amounts(ln)
        units_m = UNITS.search(ln) or UNITS.search(nxt)
        qty = float(units_m.group(1)) if units_m else None

        name: str | None = None
        conf = 0.55
        consumed_next = False
        raw = ln

        # Strategy A: instrument name alone, amounts on next line (Groww/Coin cards)
        if (
            not amounts
            and NAME_LINE.match(ln)
            and _looks_like_instrument(ln)
            and nxt
        ):
            next_amounts = _extract_amounts(nxt)
            if next_amounts:
                name = _clean_name(ln)
                amounts = next_amounts
                raw = ln + " | " + nxt
                conf = 0.72
                consumed_next = True
            elif PLAN.search(nxt) or re.search(r"rs\.?|₹|invested|current", nxt, re.I):
                # amount line may need one more hop (plan line then amounts)
                next2 = lines[i + 2] if i + 2 < len(lines) else ""
                a2 = _extract_amounts(nxt) or _extract_amounts(next2)
                if a2:
                    name = _clean_name(ln)
                    amounts = a2
                    raw = " | ".join(x for x in (ln, nxt, next2) if x)
                    conf = 0.68
                    consumed_next = True
                    if _extract_amounts(next2) and not _extract_amounts(nxt):
                        i += 1  # skip plan-only line extra

        # Strategy B: single line with amounts + name
        if name is None and amounts:
            name_part = _INR_LABELED.sub(" ", ln)
            name_part = _INR_BARE.sub(" ", name_part)
            name_part = ISIN.sub(" ", name_part)
            name_part = AMFI.sub(" ", name_part)
            name_part = UNITS.sub(" ", name_part)
            name_part = re.sub(r"[|→>]+", " ", name_part)
            name_part = _clean_name(name_part)
            if _looks_like_instrument(name_part) or (
                len(name_part) >= 4 and re.search(r"[A-Za-z]{3,}", name_part)
            ):
                name = name_part
                conf = 0.7 if isin else 0.6

        # Strategy C: ISIN on line, name nearby
        if name is None and isin:
            name_part = ISIN.sub(" ", ln)
            name_part = _INR_LABELED.sub(" ", name_part)
            name_part = _INR_BARE.sub(" ", name_part)
            name_part = _clean_name(name_part)
            if len(name_part) >= 4:
                name = name_part
                conf = 0.8
                if not amounts and nxt:
                    amounts = _extract_amounts(nxt)
                    if amounts:
                        consumed_next = True
                        raw = ln + " | " + nxt

        # Strategy D: labeled amounts only — borrow prior name line
        if name is None and amounts and i > 0:
            prev = lines[i - 1]
            if NAME_LINE.match(prev) and _looks_like_instrument(prev):
                # only if prev wasn't already used
                if not lots or lots[-1].get("source_row", {}).get("raw_line", "").startswith(prev):
                    pass
                else:
                    name = _clean_name(prev)
                    conf = 0.62
                    raw = prev + " | " + ln

        if name and amounts:
            # avoid junk names
            if HEADER_ONLY.match(name) or name.lower() in {"direct", "regular", "growth"}:
                i += 1 + (1 if consumed_next else 0)
                continue
            lot, c = _make_lot(name, amounts, raw_line=raw, isin=isin, qty=qty, conf=conf)
            lots.append(lot)
            confidences.append(c)
            if consumed_next:
                i += 2
                continue
        i += 1

    # Dedup by normalized name (keep higher value / confidence)
    best: dict[str, tuple[dict, float]] = {}
    for lot, c in zip(lots, confidences):
        k = re.sub(r"[^a-z0-9]+", "", lot["name"].lower())[:32]
        if not k:
            continue
        if k not in best or lot["current_value"] > best[k][0]["current_value"]:
            best[k] = (lot, c)

    uniq = []
    uniq_c = []
    for lot, c in best.values():
        lot = {**lot, "lot_id": f"ocr_{len(uniq)}"}
        uniq.append(lot)
        uniq_c.append(c)

    # v4: lexicon correction (AMFI + popular names) — free accuracy lift
    try:
        from .lexicon import correct_lots

        uniq = correct_lots(uniq)
        n_corr = sum(1 for l in uniq if (l.get("source_row") or {}).get("lexicon_corrected"))
    except Exception:
        n_corr = 0

    conf = sum(uniq_c) / len(uniq_c) if uniq_c else 0.1
    if n_corr and uniq:
        conf = min(0.95, conf + 0.05 * (n_corr / len(uniq)))
    return {
        "schema_version": "india_portfolio_v1",
        "source": {
            "channel": "ocr_screenshot",
            "format": "image_png",
            "parse_confidence": round(conf, 3),
            "engine": "nxance_ocr_layout_v4",
            "n_lines": len(lines),
            "n_lots": len(uniq),
            "lexicon_corrections": n_corr,
        },
        "as_of": date.today().isoformat(),
        "currency": "INR",
        "holder": {},
        "lots": uniq,
        "cashflows": [],
        "meta": {"tax_residency": "IN", "ocr_text_chars": len(text)},
    }
