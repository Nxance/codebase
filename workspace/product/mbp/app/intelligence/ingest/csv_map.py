"""India CSV / broker export fuzzy header mapping → india_portfolio_v1 lots."""
from __future__ import annotations

import csv
import io
import re
from typing import Any


HEADER_ALIASES = {
    "name": [
        "name", "scheme", "scheme_name", "fund", "fund_name", "stock", "scrip",
        "instrument", "security_name", "company",
    ],
    "isin": ["isin", "isin_code"],
    "amfi_code": ["amfi", "amfi_code", "scheme_code", "code"],
    "symbol": ["symbol", "tradingsymbol", "ticker", "nse_symbol"],
    "quantity": ["qty", "quantity", "units", "unit", "closing_balance", "balance_units"],
    "avg_cost": ["avg", "avg_price", "average_price", "avg_cost", "buy_price", "purchase_nav"],
    "invested_amount": [
        "invested", "invested_amount", "cost_value", "total_cost", "buy_value", "amount_invested",
    ],
    "current_value": [
        "current_value", "value", "market_value", "closing_value", "present_value", "current",
    ],
    "current_nav_or_price": ["nav", "ltp", "price", "cmp", "current_nav", "last_price"],
    "plan_type": ["plan", "plan_type", "option_plan"],
    "purchase_date": ["purchase_date", "buy_date", "date", "allotment_date", "trade_date"],
    "folio": ["folio", "folio_no", "folio_number"],
    "asset_class": ["asset_class", "type", "asset", "category"],
}


def _norm(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", h.strip().lower()).strip("_")


def _map_headers(headers: list[str]) -> dict[str, str]:
    """canonical_field -> actual header"""
    normed = {_norm(h): h for h in headers}
    mapping = {}
    for canon, aliases in HEADER_ALIASES.items():
        for a in aliases:
            if a in normed:
                mapping[canon] = normed[a]
                break
    return mapping


def parse_generic_csv(content: bytes | str, source_channel: str = "csv_upload") -> dict[str, Any]:
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig", errors="ignore")
    else:
        text = content
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    mapping = _map_headers(list(headers))
    lots = []
    for i, row in enumerate(reader):
        def get(canon, default=None):
            h = mapping.get(canon)
            return row.get(h, default) if h else default

        name = str(get("name") or "").strip()
        if not name:
            continue
        try:
            cur = float(str(get("current_value") or 0).replace(",", "").replace("₹", ""))
            inv = float(str(get("invested_amount") or cur).replace(",", "").replace("₹", ""))
        except Exception:
            continue
        plan_raw = str(get("plan_type") or "regular").lower()
        plan = "direct" if "direct" in plan_raw else "regular"
        ac_raw = str(get("asset_class") or "").lower()
        if "stock" in ac_raw or "equity" in ac_raw and "fund" not in ac_raw:
            asset_class = "equity_stock"
        elif "fd" in ac_raw or "deposit" in ac_raw:
            asset_class = "fd"
        elif "debt" in ac_raw:
            asset_class = "mutual_fund_debt"
        elif "elss" in ac_raw:
            asset_class = "mutual_fund_elss"
        else:
            asset_class = "mutual_fund_equity"
        try:
            qty = float(get("quantity") or 1)
        except Exception:
            qty = 1.0
        lots.append(
            {
                "lot_id": f"csv_{i}",
                "asset_class": asset_class,
                "name": name,
                "isin": get("isin"),
                "amfi_code": str(get("amfi_code") or "") or None,
                "symbol": get("symbol"),
                "quantity": qty,
                "avg_cost": float(str(get("avg_cost") or 0).replace(",", "") or 0),
                "invested_amount": inv or cur,
                "current_nav_or_price": None,
                "current_value": cur or inv,
                "plan_type": plan if "mutual" in asset_class else "na",
                "purchase_date": str(get("purchase_date") or "2021-01-01")[:10],
                "folio": get("folio"),
                "sector": "unknown",
                "market_cap_bucket": "multi",
                "source_row": dict(row),
            }
        )
    return {
        "schema_version": "india_portfolio_v1",
        "source": {
            "channel": source_channel,
            "format": "csv",
            "parse_confidence": 0.75 if mapping.get("name") else 0.4,
            "header_map": mapping,
        },
        "as_of": __import__("datetime").date.today().isoformat(),
        "currency": "INR",
        "holder": {},
        "lots": lots,
        "cashflows": [],
        "meta": {"tax_residency": "IN"},
    }
