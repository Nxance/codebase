#!/usr/bin/env python3
"""
Expand free AMFI scheme list from mfapi.in (public, no key, ₹0).

Writes data/india/amfi_seed_funds.json with popular AMC subset + existing seeds.
Also refreshes popular names used by OCR lexicon via amfi file.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "india" / "amfi_seed_funds.json"

POPULAR_AMC = re.compile(
    r"\b(parag\s*parikh|ppfas|axis|hdfc|icici|sbi|uti|mirae|nippon|kotak|"
    r"quant|motilal|bandhan|canara|dsp|franklin|invesco|edelweiss|tata|"
    r"aditya\s*birla|absli|hsbc|navi|groww|zerodha|pgim|sundaram|mahindra)\b",
    re.I,
)
STYLE = re.compile(
    r"\b(flexi|bluechip|nifty|sensex|small\s*cap|mid\s*cap|large\s*cap|"
    r"index|elss|liquid|debt|hybrid|nasdaq|multi\s*cap|focused|value)\b",
    re.I,
)


def main(limit: int = 800):
    print("Fetching free scheme list from api.mfapi.in …", flush=True)
    with urllib.request.urlopen("https://api.mfapi.in/mf", timeout=60) as r:
        all_schemes = json.loads(r.read().decode())
    print(f"  total schemes online: {len(all_schemes)}", flush=True)

    existing = []
    if OUT.exists():
        try:
            existing = json.loads(OUT.read_text())
        except Exception:
            existing = []

    # Prefer Growth / Direct when possible, popular AMCs + styles
    scored = []
    for s in all_schemes:
        name = s.get("schemeName") or ""
        code = s.get("schemeCode")
        if not name or not code:
            continue
        score = 0
        if POPULAR_AMC.search(name):
            score += 3
        if STYLE.search(name):
            score += 2
        if re.search(r"\bdirect\b", name, re.I):
            score += 1
        if re.search(r"\bgrowth\b", name, re.I):
            score += 1
        if re.search(r"\bidcw|dividend\b", name, re.I):
            score -= 1
        if score > 0:
            scored.append((score, {"schemeCode": int(code), "schemeName": name}))

    scored.sort(key=lambda x: (-x[0], x[1]["schemeName"]))
    picked = []
    seen = set()
    for _, row in scored:
        k = row["schemeCode"]
        if k in seen:
            continue
        seen.add(k)
        picked.append(row)
        if len(picked) >= limit:
            break

    for row in existing:
        k = int(row.get("schemeCode") or 0)
        if k and k not in seen:
            seen.add(k)
            picked.append({"schemeCode": k, "schemeName": row.get("schemeName") or ""})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(picked, indent=2, ensure_ascii=False))
    print(f"Wrote {len(picked)} schemes → {OUT}", flush=True)


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 800
    main(lim)
