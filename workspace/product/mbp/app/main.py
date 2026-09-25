"""
Nxance — Product-grade MBP (v2)
================================
Value-first portfolio intelligence. Guest demo without signup.
Engines compute; UI sells the insight.
"""
from __future__ import annotations

import csv
import io
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import db
from app.story import enrich_construction_story, enrich_health_story

STATIC = ROOT / "static"


def _run_health_check(*a, **k):
    from app.engines.health_check import run_health_check as fn
    return fn(*a, **k)


def _run_construction(*a, **k):
    from app.engines.construction import run_construction as fn
    return fn(*a, **k)


def _chat(*a, **k):
    from app.engines.nxancelm import chat as fn
    return fn(*a, **k)


def _explain_report(*a, **k):
    from app.engines.nxancelm import explain_report as fn
    return fn(*a, **k)


def _amfi_search(q: str):
    from app.engines.common import amfi_search as fn
    return fn(q)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="Nxance",
    version="2.0.0",
    description="AI portfolio intelligence — Minimum Buyable Product",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────────
class SignupReq(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=8, max_length=20)


class HoldingIn(BaseModel):
    name: str
    scheme_code: Optional[str] = None
    current_value: float
    invested_amount: float
    units: Optional[float] = None
    plan_type: str = "regular"
    purchase_date: str = "2021-01-01"
    asset_class: str = "mutual_fund"


class Questionnaire(BaseModel):
    goal: str = "Wealth Creation"
    target_amount: float = 2_500_000
    target_year: Optional[int] = None
    years: Optional[float] = 10
    monthly_sip: float = 10_000
    lumpsum: float = 0
    existing_savings: float = 0
    risk: str = "moderate"
    risk_response: Optional[str] = None


class HCReq(BaseModel):
    holdings: list[HoldingIn]
    questionnaire: Optional[Questionnaire] = None


class ConstructReq(BaseModel):
    questionnaire: Questionnaire


class UnlockReq(BaseModel):
    code: str


class ChatReq(BaseModel):
    message: str
    report_id: Optional[str] = None


# ── Auth ──────────────────────────────────────────────────────────
def optional_user(authorization: Optional[str]) -> Optional[dict]:
    if not authorization:
        return None
    token = authorization.replace("Bearer", "").strip()
    if not token:
        return None
    return db.get_session(token)


def require_user(authorization: Optional[str]) -> dict:
    sess = optional_user(authorization)
    if not sess:
        raise HTTPException(401, "Sign in to continue")
    return sess


def ensure_guest(authorization: Optional[str]) -> dict:
    """Auto-create guest session so value path never blocks on signup."""
    token = (authorization or "").replace("Bearer", "").strip()
    sess = optional_user(authorization)
    if sess:
        return {
            "token": token,
            "user_id": sess["user_id"],
            "name": sess.get("name"),
            "phone": sess.get("phone"),
            "unlocked": bool(sess.get("unlocked")),
        }
    user = db.create_user("Guest", "guest")
    return {
        "token": user["token"],
        "user_id": user["user_id"],
        "name": user["name"],
        "phone": user["phone"],
        "unlocked": False,
    }


def default_questionnaire() -> dict:
    return Questionnaire().model_dump()


def normalize_q(q: Optional[Questionnaire]) -> dict:
    if q is None:
        data = default_questionnaire()
    else:
        data = q.model_dump()
    if not data.get("years") and data.get("target_year"):
        from datetime import date

        data["years"] = max(0, int(data["target_year"]) - date.today().year)
    if data.get("risk_response") is None:
        data["risk_response"] = data.get("risk")
    if data.get("existing_savings") and not data.get("lumpsum"):
        data["lumpsum"] = data["existing_savings"]
    return data


# ── Core product API ──────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": "Nxance",
        "version": "2.0.0",
        "product": "portfolio_intelligence",
    }


@app.get("/api/demo/sample")
def demo_sample():
    """Canonical sample used for investor / first-run demo."""
    return {
        "label": "Typical retail portfolio (3 large-cap MFs + FD)",
        "insight_preview": "Usually surfaces Regular-plan TER leak + fund overlap",
        "holdings": _sample_holdings(),
        "questionnaire": default_questionnaire(),
    }


@app.post("/api/demo/run")
def demo_run():
    """
    One-shot path on a CANNED sample portfolio.
    Must never be framed as the visitor's personal loss.
    """
    guest = db.create_user("Demo", "demo")
    q = default_questionnaire()
    result = _run_health_check(_sample_holdings(), q, unlocked=False)
    result["is_sample"] = True
    result["sample_meta"] = {
        "label": "Built-in example portfolio",
        "why_it_shows_leaks": (
            "Sample intentionally uses Regular-plan overlapping large-cap funds "
            "so TER + overlap engines have something to demonstrate."
        ),
        "not_your_money": True,
    }
    result = enrich_health_story(result, context="sample")
    rid = db.save_report(guest["user_id"], "health_check", result, False)
    result["report_id"] = rid
    result["session"] = {
        "token": guest["token"],
        "user_id": guest["user_id"],
        "name": guest["name"],
        "unlocked": False,
    }
    db.log_event(guest["user_id"], "demo_run", {"report_id": rid, "is_sample": True})
    db.log_event(guest["user_id"], "teaser_viewed", {"report_id": rid})
    return result


@app.post("/api/health-check")
def health_check(req: HCReq, authorization: Optional[str] = Header(None)):
    sess = ensure_guest(authorization)
    unlocked = bool(sess.get("unlocked"))
    q = normalize_q(req.questionnaire)
    if not req.holdings:
        raise HTTPException(
            400,
            "Add at least one holding. Nxance never invents a personal loss without portfolio data.",
        )

    db.log_event(sess["user_id"], "portfolio_uploaded", {"n": len(req.holdings)})
    db.log_event(sess["user_id"], "questions_answered", {"engine": "health_check"})

    result = _run_health_check(
        [h.model_dump() for h in req.holdings], q, unlocked=unlocked
    )
    if result.get("error"):
        raise HTTPException(400, result["error"])
    result["is_sample"] = False
    result = enrich_health_story(result, context="user")
    rid = db.save_report(sess["user_id"], "health_check", result, unlocked)
    result["report_id"] = rid
    result["session"] = {
        "token": sess["token"],
        "user_id": sess["user_id"],
        "name": sess.get("name"),
        "unlocked": unlocked,
    }
    db.log_event(sess["user_id"], "teaser_viewed", {"report_id": rid, "is_sample": False})
    return result


@app.post("/api/construction")
def construction(req: ConstructReq, authorization: Optional[str] = Header(None)):
    sess = ensure_guest(authorization)
    unlocked = bool(sess.get("unlocked"))
    q = normalize_q(req.questionnaire)
    db.log_event(sess["user_id"], "questions_answered", {"engine": "construction"})
    result = _run_construction(q, unlocked=unlocked)
    result = enrich_construction_story(result)
    rid = db.save_report(sess["user_id"], "construction", result, unlocked)
    result["report_id"] = rid
    result["session"] = {
        "token": sess["token"],
        "user_id": sess["user_id"],
        "unlocked": unlocked,
    }
    return result


@app.post("/api/signup")
def signup(req: SignupReq, authorization: Optional[str] = Header(None)):
    """Upgrade guest → named user, keep unlock state if same browser session is new."""
    user = db.create_user(req.name.strip(), req.phone.strip())
    # If previous guest was unlocked, user must re-unlock — simple MBP
    return {
        **user,
        "message": "Account ready. Goal questions only appear inside each engine.",
    }


@app.get("/api/me")
def me(authorization: Optional[str] = Header(None)):
    sess = require_user(authorization)
    return {
        "user_id": sess["user_id"],
        "name": sess["name"],
        "phone": sess["phone"],
        "unlocked": bool(sess["unlocked"]),
    }


@app.post("/api/unlock")
def unlock(req: UnlockReq, authorization: Optional[str] = Header(None)):
    sess = ensure_guest(authorization)
    db.log_event(sess["user_id"], "pay_clicked", {"code_attempt": req.code[:24]})
    ok = db.set_unlocked(sess["user_id"], req.code)
    if not ok:
        raise HTTPException(
            400,
            "Invalid code. After UPI payment, ask founder for a code. Demo: DEMO-UNLOCK",
        )
    return {
        "unlocked": True,
        "session": {
            "token": sess["token"],
            "user_id": sess["user_id"],
            "unlocked": True,
        },
        "message": "Full intelligence unlocked. Re-run any engine for complete output.",
    }


@app.post("/api/chat")
def chat_api(req: ChatReq, authorization: Optional[str] = Header(None)):
    sess = ensure_guest(authorization)
    report = None
    if req.report_id:
        rep = db.get_report(req.report_id, sess["user_id"])
        if rep:
            report = rep["payload"]
    return _chat(req.message, report)


@app.post("/api/explain")
def explain(report_id: str, authorization: Optional[str] = Header(None)):
    sess = ensure_guest(authorization)
    rep = db.get_report(report_id, sess["user_id"])
    if not rep:
        raise HTTPException(404, "Report not found")
    return _explain_report(rep["payload"])


@app.get("/api/sample-portfolio")
def sample_portfolio():
    return {"holdings": _sample_holdings()}


@app.get("/api/search")
def search(q: str):
    results = _amfi_search(q)
    return {
        "results": [
            {
                "scheme_code": str(r.get("schemeCode", "")),
                "name": r.get("schemeName", ""),
            }
            for r in results
        ]
    }


@app.get("/api/admin/funnel")
def funnel(authorization: Optional[str] = Header(None)):
    ensure_guest(authorization)
    return db.funnel_stats()


def _norm_key(k: str) -> str:
    return str(k).strip().lower().replace(" ", "_").replace("-", "_")


def _rows_from_dicts(dicts: list[dict]) -> list[dict]:
    rows = []
    for r in dicts:
        r = {_norm_key(k): v for k, v in r.items()}
        nm = str(
            r.get("fund_name") or r.get("fund") or r.get("name") or r.get("scheme") or ""
        ).strip()
        if not nm or nm == "nan":
            continue
        try:
            val = float(
                str(r.get("current_value") or r.get("value") or 0)
                .replace(",", "")
                .replace("₹", "")
            )
            inv = float(
                str(r.get("invested_amount") or r.get("invested") or val)
                .replace(",", "")
                .replace("₹", "")
            )
            plan = (
                "direct"
                if "direct"
                in str(r.get("plan_type") or r.get("plan") or "regular").lower()
                else "regular"
            )
            pdate = str(r.get("purchase_date") or r.get("date") or "2021-01-01")[:10]
            units = r.get("units")
            try:
                units = float(units) if units not in (None, "", "nan") else None
            except Exception:
                units = None
            scheme = (
                str(r.get("scheme_code") or r.get("amfi_code") or "").strip() or None
            )
            asset = str(r.get("asset_class") or "mutual_fund").lower()
            if "stock" in asset:
                asset = "stock"
            elif "fd" in asset or "deposit" in asset:
                asset = "fd"
            else:
                asset = "mutual_fund"
        except Exception:
            continue
        if val > 0 or inv > 0:
            rows.append(
                {
                    "name": nm,
                    "scheme_code": scheme,
                    "current_value": val or inv,
                    "invested_amount": inv or val,
                    "units": units,
                    "plan_type": plan,
                    "purchase_date": pdate,
                    "asset_class": asset,
                }
            )
    return rows


@app.post("/api/parse-excel")
async def parse_excel(file: UploadFile = File(...)):
    """Legacy simple parse + India canonical path for CSV."""
    content = await file.read()
    name = (file.filename or "").lower()
    try:
        if name.endswith(".csv"):
            from app.intelligence.ingest.csv_map import parse_generic_csv
            from app.intelligence.ingest.canonical import (
                lots_to_engine_holdings,
                validate_minimal,
            )

            doc = parse_generic_csv(content, source_channel="csv_upload")
            errs = validate_minimal(doc)
            holdings = lots_to_engine_holdings(doc.get("lots") or [])
            if not holdings:
                # fallback old path
                text = content.decode("utf-8-sig", errors="ignore")
                reader = csv.DictReader(io.StringIO(text))
                dicts = list(reader)
                holdings = _rows_from_dicts(dicts)
            return {
                "holdings": holdings,
                "count": len(holdings),
                "canonical": doc,
                "validation_errors": errs,
                "india_schema": "india_portfolio_v1",
            }
        else:
            from openpyxl import load_workbook

            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            rows_iter = ws.iter_rows(values_only=True)
            headers = [str(h or "") for h in next(rows_iter)]
            dicts = []
            for row in rows_iter:
                dicts.append(
                    {
                        headers[i]: row[i]
                        for i in range(len(headers))
                        if i < len(row)
                    }
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Cannot read file: {e}")
    rows = _rows_from_dicts(dicts)
    if not rows:
        raise HTTPException(400, "No valid rows found")
    return {"holdings": rows, "count": len(rows)}


@app.post("/api/ingest/cas-text")
async def ingest_cas_text(payload: dict):
    """Ingest plain-text CAS / statement dump → canonical + engine holdings."""
    from app.intelligence.ingest.cas_stub import parse_cas_text
    from app.intelligence.ingest.canonical import lots_to_engine_holdings, validate_minimal

    text = payload.get("text") or ""
    channel = payload.get("channel") or "cas_cams"
    doc = parse_cas_text(text, channel=channel)
    return {
        "canonical": doc,
        "validation_errors": validate_minimal(doc),
        "holdings": lots_to_engine_holdings(doc.get("lots") or []),
        "count": len(doc.get("lots") or []),
    }


@app.post("/api/ingest/ocr-text")
async def ingest_ocr_text(payload: dict):
    """OCR text (from screenshot pipeline) → same India schema."""
    from app.intelligence.ingest.ocr_stub import parse_ocr_text
    from app.intelligence.ingest.canonical import lots_to_engine_holdings, validate_minimal

    doc = parse_ocr_text(payload.get("text") or "", channel=payload.get("channel") or "ocr_screenshot")
    return {
        "canonical": doc,
        "validation_errors": validate_minimal(doc),
        "holdings": lots_to_engine_holdings(doc.get("lots") or []),
        "count": len(doc.get("lots") or []),
    }


@app.get("/api/training/status")
def training_status():
    """Report synthetic data + model bundle readiness (lazy, memory-safe)."""
    from pathlib import Path
    from app.intelligence.ml.trained import load_bundle, resolve_bundle_path
    from app.intelligence.dl.models import deep_status
    from app.intelligence.ocr.engine import ocr_available

    root = Path(__file__).resolve().parent.parent
    syn = root / "data" / "synthetic"
    bundle = load_bundle()
    models = (bundle or {}).get("models") or {}
    boost_tasks = [
        k for k, m in models.items() if isinstance(m, dict) and m.get("boost_stumps")
    ]
    bpath = resolve_bundle_path()
    return {
        "synthetic": {
            "features_train": (syn / "features_train.csv").exists(),
            "portfolios_train": (syn / "portfolios_train.jsonl").exists(),
            "meta": (syn / "labels_meta.json").exists(),
        },
        "model_bundle": {
            "path": bpath.name,
            "loaded": bundle is not None,
            "version": (bundle or {}).get("version"),
            "models": list(models.keys()),
            "boost_tasks": boost_tasks,
            "n_features": len((bundle or {}).get("feature_columns") or []),
        },
        "deep_models": deep_status(),
        "ocr": ocr_available(),
        "schema": "india_portfolio_v1",
        "amfi_seeds": (root / "data" / "india" / "amfi_seed_funds.json").exists(),
        "cost": "zero",
        "stack": "L1 quant · L2 bags+boost · L3 emb+style · OCR v4",
    }


@app.get("/api/deep/embed")
def deep_embed(name: str, category: str = ""):
    from app.intelligence.dl.models import embed_fund

    return embed_fund(name, category)


@app.get("/api/deep/similarity")
def deep_sim(a: str, b: str):
    from app.intelligence.dl.models import similarity

    return {"a": a, "b": b, "similarity": similarity(a, b), "layer": "L3_dl"}


@app.get("/api/deep/status")
def deep_status_api():
    from app.intelligence.dl.models import deep_status

    return deep_status()


@app.post("/api/deep/overlap")
def deep_overlap_api(payload: dict):
    """L3 embedding-style fund overlap for a list of holdings."""
    from app.intelligence.dl.models import portfolio_embedding_overlap

    holdings = payload.get("holdings") or []
    thr = float(payload.get("threshold") or 0.72)
    return portfolio_embedding_overlap(holdings, threshold=thr)


@app.get("/api/ocr/status")
def ocr_status():
    from app.intelligence.ocr.engine import ocr_available

    return {"cost": "zero", **ocr_available()}


@app.post("/api/ocr/image")
async def ocr_image(file: UploadFile = File(...)):
    """
    Zero-cost OCR: image → india_portfolio_v1 + engine holdings.
    Uses Tesseract (free) + Pillow preprocess + India layout parser.
    """
    from app.intelligence.ocr.engine import ocr_image_bytes
    from app.intelligence.ingest.canonical import lots_to_engine_holdings, validate_minimal

    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty image")
    doc = ocr_image_bytes(data)
    lots = doc.get("lots") or []
    holdings = lots_to_engine_holdings(lots)
    return {
        "canonical": {k: v for k, v in doc.items() if k != "ocr_text"},
        "ocr_text_preview": (doc.get("ocr_text") or "")[:2000],
        "validation_errors": validate_minimal(doc),
        "holdings": holdings,
        "count": len(holdings),
        "cost": "zero",
    }


@app.post("/api/ocr/text")
async def ocr_text_parse(payload: dict):
    """Parse already-extracted text (from any OCR) into holdings."""
    from app.intelligence.ocr.layout import parse_holdings_from_ocr_text
    from app.intelligence.ingest.canonical import lots_to_engine_holdings, validate_minimal

    text = payload.get("text") or ""
    doc = parse_holdings_from_ocr_text(text)
    return {
        "canonical": doc,
        "validation_errors": validate_minimal(doc),
        "holdings": lots_to_engine_holdings(doc.get("lots") or []),
        "count": len(doc.get("lots") or []),
        "cost": "zero",
    }


@app.post("/api/pdf/extract")
async def pdf_extract(file: UploadFile = File(...)):
    """Zero-cost PDF text extract → CAS/layout parse → holdings."""
    from app.intelligence.ingest.document import ingest_document

    data = await file.read()
    result = ingest_document(
        data, filename=file.filename or "statement.pdf", content_type=file.content_type or ""
    )
    return result


@app.post("/api/ingest/document")
async def ingest_document_api(file: UploadFile = File(...)):
    """
    Universal document upload (₹0 stack).

    Accepts: PDF, XLSX, CSV, TSV, TXT, JSON, PNG/JPG/WEBP (OCR), CAS dumps.
    Returns india_portfolio_v1 + engine holdings.
    """
    from app.intelligence.ingest.document import ingest_document, SUPPORTED

    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 25MB for free local parse)")
    result = ingest_document(
        data,
        filename=file.filename or "upload.bin",
        content_type=file.content_type or "",
    )
    result["supported_formats"] = sorted(SUPPORTED.keys())
    return result


@app.get("/api/ingest/formats")
def ingest_formats():
    from app.intelligence.ingest.document import SUPPORTED

    return {
        "formats": sorted(SUPPORTED.keys()),
        "kinds": sorted(set(SUPPORTED.values())),
        "notes": {
            "pdf": "CAS / MF statement text via pdfminer",
            "excel": "XLSX via openpyxl (save legacy .xls as .xlsx)",
            "csv": "Broker exports, Groww/Coin CSV",
            "image": "Screenshot OCR via Tesseract",
            "json": "india_portfolio_v1 or holdings[]",
            "text": "Pasted CAS or OCR text",
        },
        "cost": "zero",
    }


# ── Dummy payments (no Razorpay — free MBP) ───────────────────────
class PayCreateReq(BaseModel):
    amount_inr: float = 99.0
    method: str = "dummy_upi"


class PayConfirmReq(BaseModel):
    payment_id: str


@app.post("/api/payments/create")
def payment_create(req: PayCreateReq, authorization: Optional[str] = Header(None)):
    sess = ensure_guest(authorization)
    pay = db.create_payment(
        sess["user_id"], amount_inr=float(req.amount_inr or 99), method=req.method or "dummy_upi"
    )
    return {
        **pay,
        "session": {
            "token": sess["token"],
            "user_id": sess["user_id"],
            "unlocked": bool(sess.get("unlocked")),
        },
        "plans": [
            {"id": "unlock_99", "title": "Full intelligence unlock", "amount_inr": 99},
            {"id": "unlock_demo", "title": "Demo code (no pay)", "amount_inr": 0, "code": "DEMO-UNLOCK"},
        ],
    }


@app.post("/api/payments/confirm")
def payment_confirm(req: PayConfirmReq, authorization: Optional[str] = Header(None)):
    sess = ensure_guest(authorization)
    out = db.confirm_payment(req.payment_id, sess["user_id"])
    if not out:
        raise HTTPException(404, "Payment not found")
    return {
        **out,
        "session": {
            "token": sess["token"],
            "user_id": sess["user_id"],
            "unlocked": True,
        },
    }


@app.get("/api/payments/{payment_id}")
def payment_get(payment_id: str, authorization: Optional[str] = Header(None)):
    sess = ensure_guest(authorization)
    row = db.get_payment(payment_id, sess["user_id"])
    if not row:
        raise HTTPException(404, "Payment not found")
    return {
        "payment_id": row["id"],
        "amount_inr": row["amount_inr"],
        "method": row["method"],
        "status": row["status"],
        "unlock_code": row.get("unlock_code"),
        "created_at": row.get("created_at"),
        "confirmed_at": row.get("confirmed_at"),
    }


@app.post("/api/login")
def login(req: SignupReq):
    """
    Dummy login = create/replace session for name+phone (no OTP, free MBP).
    Same as signup for simplicity; production would verify OTP.
    """
    user = db.create_user(req.name.strip(), req.phone.strip())
    return {
        **user,
        "message": "Logged in (demo auth — no OTP). Use Payments or DEMO-UNLOCK for full report.",
        "session": {
            "token": user["token"],
            "user_id": user["user_id"],
            "name": user["name"],
            "unlocked": False,
        },
    }


def _sample_holdings() -> list[dict]:
    return [
        {
            "name": "Axis Bluechip Regular",
            "scheme_code": "120505",
            "current_value": 185000,
            "invested_amount": 120000,
            "plan_type": "regular",
            "purchase_date": "2020-02-10",
            "asset_class": "mutual_fund",
        },
        {
            "name": "Mirae Asset Large Cap Regular",
            "scheme_code": "118834",
            "current_value": 142000,
            "invested_amount": 100000,
            "plan_type": "regular",
            "purchase_date": "2019-08-15",
            "asset_class": "mutual_fund",
        },
        {
            "name": "HDFC Flexi Cap Regular",
            "scheme_code": "118989",
            "current_value": 168000,
            "invested_amount": 130000,
            "plan_type": "regular",
            "purchase_date": "2018-11-01",
            "asset_class": "mutual_fund",
        },
        {
            "name": "SBI FD 3yr",
            "current_value": 112000,
            "invested_amount": 100000,
            "plan_type": "regular",
            "purchase_date": "2023-01-01",
            "asset_class": "fd",
        },
    ]


# ── Frontend ──────────────────────────────────────────────────────
if STATIC.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC)), name="assets")
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
def index():
    path = STATIC / "index.html"
    if not path.exists():
        return {"error": "UI missing"}
    return FileResponse(path)


@app.get("/how-to-use")
@app.get("/how_to_use.html")
def how_to_use():
    """Internal team walkthrough — screen-by-screen how to use."""
    path = STATIC / "how_to_use.html"
    if not path.exists():
        raise HTTPException(404, "how_to_use.html missing")
    return FileResponse(path)


@app.get("/demo")
@app.get("/demo_tour.html")
def demo_tour():
    """Self-playing live product demo (Abhiyan-style client walkthrough)."""
    path = STATIC / "demo_tour.html"
    if not path.exists():
        raise HTTPException(404, "demo_tour.html missing")
    return FileResponse(path)


@app.get("/sample_portfolio.csv")
def sample_csv():
    path = STATIC / "sample_portfolio.csv"
    if not path.exists():
        raise HTTPException(404, "sample missing")
    return FileResponse(path)


def main():
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    print(f"\n  Nxance v2  →  http://127.0.0.1:{port}\n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
