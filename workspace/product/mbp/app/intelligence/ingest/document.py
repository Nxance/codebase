"""
Unified zero-cost document ingest.

Formats (all free local parsers):
  - PDF  → pdfminer text → CAS + layout parse
  - XLSX → openpyxl
  - XLS  → try openpyxl / binary rejection with clear message
  - CSV / TSV / TXT → csv or layout/CAS text
  - JSON → india_portfolio_v1 or holdings[]
  - PNG / JPG / JPEG / WEBP / BMP / TIFF → Tesseract OCR

No paid SaaS. Schema always india_portfolio_v1 + engine holdings.
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import date
from typing import Any, Optional


SUPPORTED = {
    ".pdf": "pdf",
    ".xlsx": "excel",
    ".xlsm": "excel",
    ".xls": "excel_legacy",
    ".csv": "csv",
    ".tsv": "tsv",
    ".txt": "text",
    ".json": "json",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".bmp": "image",
    ".tif": "image",
    ".tiff": "image",
    ".heic": "image",
}


def detect_kind(filename: str, content_type: str = "") -> str:
    name = (filename or "").lower().strip()
    for ext, kind in SUPPORTED.items():
        if name.endswith(ext):
            return kind
    ct = (content_type or "").lower()
    if "pdf" in ct:
        return "pdf"
    if "spreadsheet" in ct or "excel" in ct:
        return "excel"
    if "csv" in ct:
        return "csv"
    if "json" in ct:
        return "json"
    if "image" in ct:
        return "image"
    if "text" in ct:
        return "text"
    # magic bytes
    return "unknown"


def _empty_doc(channel: str, note: str = "") -> dict[str, Any]:
    return {
        "schema_version": "india_portfolio_v1",
        "source": {
            "channel": channel,
            "parse_confidence": 0.0,
            "notes": note,
        },
        "as_of": date.today().isoformat(),
        "currency": "INR",
        "holder": {},
        "lots": [],
        "cashflows": [],
        "meta": {"tax_residency": "IN"},
    }


def _merge_lots(*docs: dict) -> dict[str, Any]:
    """Pick the doc with most lots / highest confidence."""
    best = None
    best_score = -1.0
    for d in docs:
        if not d:
            continue
        n = len(d.get("lots") or [])
        conf = float((d.get("source") or {}).get("parse_confidence") or 0)
        sc = n * 2 + conf
        if sc > best_score:
            best_score = sc
            best = d
    return best or _empty_doc("none", "no parse")


def _parse_text_blob(text: str, channel: str = "text_upload") -> dict[str, Any]:
    from app.intelligence.ingest.cas_stub import parse_cas_text
    from app.intelligence.ocr.layout import parse_holdings_from_ocr_text

    cas = parse_cas_text(text, channel=channel)
    layout = parse_holdings_from_ocr_text(text)
    layout["source"]["channel"] = channel
    return _merge_lots(cas, layout)


def parse_pdf(data: bytes) -> dict[str, Any]:
    text = ""
    backend = "none"
    try:
        from pdfminer.high_level import extract_text

        text = extract_text(io.BytesIO(data)) or ""
        backend = "pdfminer"
    except Exception as e:
        try:
            text = data.decode("utf-8", errors="ignore")
            backend = f"utf8_fallback:{e}"
        except Exception:
            doc = _empty_doc("cas_pdf", f"pdf extract failed: {e}")
            doc["source"]["pdf_backend"] = "failed"
            return doc
    doc = _parse_text_blob(text, channel="cas_pdf")
    doc["source"]["pdf_backend"] = backend
    doc["source"]["format"] = "pdf"
    doc["meta"]["text_chars"] = len(text)
    doc["meta"]["text_preview"] = text[:1500]
    return doc


def parse_excel(data: bytes, filename: str = "") -> dict[str, Any]:
    from app.intelligence.ingest.csv_map import parse_generic_csv
    from app.intelligence.ingest.canonical import engine_holdings_to_lots

    # If someone sent CSV bytes with xlsx name, try csv first
    if filename.lower().endswith((".csv", ".tsv")):
        return parse_generic_csv(data, source_channel="csv_upload")

    try:
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        headers = [str(h or "").strip() for h in next(rows_iter)]
        # Serialize to CSV for shared mapper
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(headers)
        for row in rows_iter:
            w.writerow(["" if c is None else c for c in row])
        doc = parse_generic_csv(buf.getvalue().encode("utf-8"), source_channel="excel_upload")
        doc["source"]["format"] = "xlsx"
        doc["source"]["excel_backend"] = "openpyxl"
        return doc
    except Exception as e:
        # Legacy .xls not supported without xlrd — clear message
        if filename.lower().endswith(".xls"):
            doc = _empty_doc(
                "excel_upload",
                "Legacy .xls not supported offline. Save as .xlsx or .csv (Excel → Save As).",
            )
            doc["source"]["error"] = str(e)
            return doc
        doc = _empty_doc("excel_upload", f"Excel parse failed: {e}")
        return doc


def parse_csv_bytes(data: bytes, *, tsv: bool = False) -> dict[str, Any]:
    from app.intelligence.ingest.csv_map import parse_generic_csv

    if tsv:
        # normalize tabs → commas for mapper if needed
        try:
            text = data.decode("utf-8-sig", errors="ignore")
            # if already comma CSV, pass through
            if "\t" in text.splitlines()[0] if text.splitlines() else False:
                reader = csv.reader(io.StringIO(text), delimiter="\t")
                rows = list(reader)
                buf = io.StringIO()
                w = csv.writer(buf)
                w.writerows(rows)
                data = buf.getvalue().encode("utf-8")
        except Exception:
            pass
    return parse_generic_csv(data, source_channel="csv_upload")


def parse_json_bytes(data: bytes) -> dict[str, Any]:
    from app.intelligence.ingest.canonical import engine_holdings_to_lots

    try:
        obj = json.loads(data.decode("utf-8"))
    except Exception as e:
        return _empty_doc("json_upload", f"invalid json: {e}")

    if isinstance(obj, dict) and (obj.get("lots") or obj.get("schema_version")):
        obj.setdefault("schema_version", "india_portfolio_v1")
        obj.setdefault("source", {"channel": "json_upload", "parse_confidence": 0.9})
        obj.setdefault("lots", [])
        return obj

    holdings = []
    if isinstance(obj, list):
        holdings = obj
    elif isinstance(obj, dict):
        holdings = obj.get("holdings") or obj.get("portfolio") or []

    lots = []
    if holdings and isinstance(holdings, list):
        # convert engine-style holdings if present
        try:
            lots = engine_holdings_to_lots(holdings)
        except Exception:
            lots = []
        if not lots:
            for i, h in enumerate(holdings):
                if not isinstance(h, dict):
                    continue
                name = str(h.get("name") or h.get("scheme") or "").strip()
                if not name:
                    continue
                cv = float(h.get("current_value") or h.get("value") or 0)
                inv = float(h.get("invested_amount") or h.get("invested") or cv)
                lots.append(
                    {
                        "lot_id": f"json_{i}",
                        "asset_class": str(h.get("asset_class") or "mutual_fund_equity"),
                        "name": name,
                        "isin": h.get("isin"),
                        "amfi_code": h.get("scheme_code") or h.get("amfi_code"),
                        "quantity": float(h.get("units") or 1),
                        "avg_cost": 0,
                        "invested_amount": inv,
                        "current_value": cv or inv,
                        "plan_type": h.get("plan_type") or "regular",
                        "purchase_date": str(h.get("purchase_date") or "2022-01-01")[:10],
                        "sector": "unknown",
                        "market_cap_bucket": "multi",
                        "source_row": h,
                    }
                )
    return {
        "schema_version": "india_portfolio_v1",
        "source": {
            "channel": "json_upload",
            "format": "json",
            "parse_confidence": 0.85 if lots else 0.1,
        },
        "as_of": date.today().isoformat(),
        "currency": "INR",
        "holder": {},
        "lots": lots,
        "cashflows": [],
        "meta": {"tax_residency": "IN"},
    }


def parse_image(data: bytes) -> dict[str, Any]:
    from app.intelligence.ocr.engine import ocr_image_bytes

    return ocr_image_bytes(data)


def ingest_document(
    data: bytes,
    *,
    filename: str = "",
    content_type: str = "",
) -> dict[str, Any]:
    """
    Returns {
      kind, filename, canonical, holdings, count, validation_errors,
      supported_formats, cost
    }
    """
    from app.intelligence.ingest.canonical import lots_to_engine_holdings, validate_minimal

    kind = detect_kind(filename, content_type)
    if kind == "unknown" and data[:4] == b"%PDF":
        kind = "pdf"
    if kind == "unknown" and data[:8] == b"\x89PNG\r\n\x1a\n":
        kind = "image"
    if kind == "unknown" and data[:2] == b"\xff\xd8":
        kind = "image"

    if kind == "pdf":
        doc = parse_pdf(data)
    elif kind == "excel":
        doc = parse_excel(data, filename)
    elif kind == "excel_legacy":
        doc = parse_excel(data, filename or "file.xls")
    elif kind == "csv":
        doc = parse_csv_bytes(data)
    elif kind == "tsv":
        doc = parse_csv_bytes(data, tsv=True)
    elif kind == "json":
        doc = parse_json_bytes(data)
    elif kind == "image":
        doc = parse_image(data)
    elif kind == "text":
        try:
            text = data.decode("utf-8-sig", errors="ignore")
        except Exception:
            text = ""
        doc = _parse_text_blob(text, channel="text_upload")
    else:
        # last resort: try text decode then image
        try:
            text = data.decode("utf-8-sig", errors="strict")
            if len(text) > 20 and sum(c.isprintable() or c.isspace() for c in text) / max(
                1, len(text)
            ) > 0.85:
                doc = _parse_text_blob(text, channel="text_upload")
                kind = "text"
            else:
                doc = parse_image(data)
                kind = "image"
        except Exception:
            doc = parse_image(data)
            kind = "image"

    lots = doc.get("lots") or []
    holdings = lots_to_engine_holdings(lots)
    return {
        "kind": kind,
        "filename": filename,
        "canonical": {k: v for k, v in doc.items() if k not in ("ocr_text",)},
        "ocr_text_preview": (doc.get("ocr_text") or doc.get("meta", {}).get("text_preview") or "")[
            :2000
        ],
        "validation_errors": validate_minimal(doc),
        "holdings": holdings,
        "count": len(holdings),
        "supported_formats": sorted(SUPPORTED.keys()),
        "cost": "zero",
        "engine": "nxance_ingest_v1",
    }
