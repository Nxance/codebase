"""
Zero-cost OCR lexicon — correct garbled fund/stock names using free local data.

Sources (all free):
  - AMFI seed schemes (bundled)
  - Popular India fund/stock short names (hardcoded priors)
  - Common OCR character confusions (0/O, l/1, rn/m, …)

No paid APIs, no cloud spellcheck.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[3]
AMFI_PATH = ROOT / "data" / "india" / "amfi_seed_funds.json"

# High-frequency retail holdings in India apps (Groww / Coin / MF Central)
POPULAR = [
    "Parag Parikh Flexi Cap Fund",
    "Axis Bluechip Fund",
    "HDFC Flexi Cap Fund",
    "HDFC Mid-Cap Opportunities Fund",
    "UTI Nifty 50 Index Fund",
    "UTI Nifty 50 ETF",
    "SBI Small Cap Fund",
    "SBI Bluechip Fund",
    "Mirae Asset Large Cap Fund",
    "Mirae Asset Emerging Bluechip Fund",
    "ICICI Prudential Bluechip Fund",
    "ICICI Prudential Technology Fund",
    "Nippon India Large Cap Fund",
    "Nippon India Small Cap Fund",
    "Kotak Emerging Equity Fund",
    "Kotak Flexicap Fund",
    "Quant Small Cap Fund",
    "Quant Active Fund",
    "Motilal Oswal Nasdaq 100 Fund of Fund",
    "Motilal Oswal Midcap Fund",
    "Canara Robeco Bluechip Equity Fund",
    "Bandhan Small Cap Fund",
    "PPFAS Long Term Equity Fund",
    "HDFC Bank Ltd",
    "ICICI Bank Ltd",
    "Reliance Industries Ltd",
    "Infosys Ltd",
    "TCS Ltd",
    "Bharti Airtel Ltd",
    "SBI Fixed Deposit",
    "HDFC Fixed Deposit",
]

OCR_SUBS = [
    (r"0", "o"),
    (r"1", "l"),
    (r"5", "s"),
    (r"rn", "m"),
    (r"cl", "d"),
    (r"vv", "w"),
    (r"ii", "n"),
]


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\b(fund|direct|regular|growth|plan|option|idcw|dividend)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _ocr_fold(s: str) -> str:
    t = _norm(s)
    for a, b in OCR_SUBS:
        t = re.sub(a, b, t)
    return t


def _tokens(s: str) -> set[str]:
    return {t for t in _norm(s).split() if len(t) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _char_sim(a: str, b: str) -> float:
    """Cheap character bigram Dice coefficient (no third-party deps)."""
    a, b = _ocr_fold(a), _ocr_fold(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ba = {a[i : i + 2] for i in range(len(a) - 1)} or {a}
    bb = {b[i : i + 2] for i in range(len(b) - 1)} or {b}
    inter = len(ba & bb)
    return (2.0 * inter) / (len(ba) + len(bb))


@lru_cache(maxsize=1)
def load_lexicon() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(name: str, *, amfi: Optional[int] = None, kind: str = "fund"):
        n = name.strip()
        if not n:
            return
        key = _norm(n)
        if not key or key in seen:
            return
        seen.add(key)
        entries.append(
            {
                "name": n,
                "norm": key,
                "fold": _ocr_fold(n),
                "tokens": frozenset(_tokens(n)),
                "amfi_code": amfi,
                "kind": kind,
            }
        )

    for p in POPULAR:
        kind = "fd" if "deposit" in p.lower() else ("stock" if "ltd" in p.lower() else "fund")
        add(p, kind=kind)

    if AMFI_PATH.exists():
        try:
            for s in json.loads(AMFI_PATH.read_text()):
                name = s.get("schemeName") or ""
                code = s.get("schemeCode")
                add(name, amfi=int(code) if code else None, kind="fund")
                # short form without plan suffix
                short = re.sub(
                    r"\s*[-–]\s*(Direct|Regular).*$",
                    "",
                    name,
                    flags=re.I,
                )
                add(short, amfi=int(code) if code else None, kind="fund")
        except Exception:
            pass
    return entries


def clear_lexicon_cache() -> None:
    load_lexicon.cache_clear()


def correct_name(raw: str, *, min_score: float = 0.42) -> dict[str, Any]:
    """
    Map OCR-garbled name → best lexicon match.
    Returns original when no confident match.
    """
    raw = (raw or "").strip()
    if len(raw) < 3:
        return {
            "name": raw,
            "corrected": False,
            "score": 0.0,
            "match": None,
            "amfi_code": None,
        }

    lex = load_lexicon()
    raw_tok = _tokens(raw)
    raw_fold = _ocr_fold(raw)
    best = None
    best_score = 0.0

    for e in lex:
        # token overlap + character fold similarity
        j = _jaccard(raw_tok, set(e["tokens"]))
        c = _char_sim(raw_fold, e["fold"])
        # prefix bonus for partial OCR of long fund names
        pref = 0.0
        rn, en = _norm(raw), e["norm"]
        if rn and en and (rn[:8] in en or en[:8] in rn):
            pref = 0.15
        score = 0.55 * j + 0.35 * c + pref
        if score > best_score:
            best_score = score
            best = e

    if best is None or best_score < min_score:
        return {
            "name": raw,
            "corrected": False,
            "score": round(best_score, 3),
            "match": None,
            "amfi_code": None,
        }

    # Preserve plan hint from raw if lexicon stripped it
    out_name = best["name"]
    low = raw.lower()
    if "direct" in low and "direct" not in out_name.lower():
        out_name = out_name + " Direct"
    elif "regular" in low and "regular" not in out_name.lower():
        out_name = out_name + " Regular"

    return {
        "name": out_name,
        "corrected": out_name.lower() != raw.lower(),
        "score": round(best_score, 3),
        "match": best["name"],
        "amfi_code": best.get("amfi_code"),
        "kind": best.get("kind"),
    }


def correct_lots(lots: list[dict]) -> list[dict]:
    """In-place-safe correction of lot names + AMFI fill."""
    out = []
    for lot in lots:
        fixed = correct_name(str(lot.get("name") or ""))
        row = {**lot}
        if fixed["corrected"] or fixed.get("amfi_code"):
            row["name"] = fixed["name"][:80]
            row["ocr_name_raw"] = lot.get("name")
            row["ocr_name_score"] = fixed["score"]
            if fixed.get("amfi_code") and not row.get("amfi_code"):
                row["amfi_code"] = fixed["amfi_code"]
            src = dict(row.get("source_row") or {})
            src["lexicon_corrected"] = fixed["corrected"]
            src["lexicon_score"] = fixed["score"]
            row["source_row"] = src
        out.append(row)
    return out
