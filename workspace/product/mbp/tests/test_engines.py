"""Smoke tests for layered intelligence + MBP engines."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engines.fraud import run_fraud_gate
from app.engines.health_check import run_health_check
from app.engines.construction import run_construction
from app.engines.nxancelm import chat, explain_report, intent_route
from app.intelligence.nlp.guard import number_guard
from app.intelligence.quant.metrics import hhi, required_return_pct, xirr
from app.intelligence.ml.scorer import FundQualityScorer
from app.intelligence.dl.embeddings import FundEmbedder
from app.intelligence.optimize.allocation import strategic_allocation


def test_xirr_basic():
    r = xirr([-10000, 15000], [date(2020, 1, 1), date(2025, 1, 1)])
    assert r is not None and 5 < r < 20


def test_required_return():
    r0 = required_return_pct(1_000_000, 100_000, 10_000, 8)
    assert r0 is not None and r0 == 0.0
    r = required_return_pct(5_000_000, 100_000, 10_000, 8)
    assert r is not None and 0 < r <= 30.01


def test_hhi():
    assert hhi([0.5, 0.5]) == 0.5


def test_fraud_critical():
    f = run_fraud_gate(
        [
            {
                "name": "guaranteed triple crypto pump",
                "invested_amount": 1000,
                "current_value": 5000,
                "xirr": 120,
                "asset_class": "mutual_fund",
            }
        ]
    )
    assert f["critical"] is True


def test_ml_scorer():
    s = FundQualityScorer()
    p = s.predict({"ter": 1.5, "xirr": 11, "plan_regular": 1, "underperform_vs_port": 0, "is_fd": 0})
    assert 0 <= p["score"] <= 100
    assert p["layer"] == "L2_ml"


def test_dl_embedder():
    e = FundEmbedder()
    a = e.embed("UTI Nifty 50 Index", "index")
    b = e.embed("HDFC Flexi Cap", "flexi")
    assert len(a) in (32, 48)  # hash fallback 32 or trained 48
    assert len(a) == len(b)
    assert e.similarity(a, a) > 0.99


def test_style_factors_and_overlap():
    from app.intelligence.dl.style_factors import style_similarity, style_labels
    from app.intelligence.dl.models import portfolio_embedding_overlap

    assert style_similarity("Axis Bluechip Fund", "ICICI Bluechip Fund") > 0.5
    labs = style_labels("SBI Small Cap Fund Direct")
    assert "small_cap" in labs or "direct_plan" in labs
    ov = portfolio_embedding_overlap(
        [
            {"name": "Axis Bluechip Fund Direct", "asset_class": "mutual_fund"},
            {"name": "ICICI Prudential Bluechip Fund Direct", "asset_class": "mutual_fund"},
            {"name": "HDFC Bank Ltd", "asset_class": "stock"},
        ]
    )
    assert ov["layer"] == "L3_dl"
    assert "style_histogram" in ov
    assert ov["method"] == "embedding_x_style_v4"


def test_ocr_lexicon_and_layout():
    from app.intelligence.ocr.lexicon import correct_name
    from app.intelligence.ocr.layout import parse_holdings_from_ocr_text

    fixed = correct_name("Parag Parlkh Flexi Cap", min_score=0.35)
    assert "parikh" in fixed["name"].lower() or "parag" in fixed["name"].lower()
    text = (
        "My Investments\n"
        "Axis Bluechip Fund\n"
        "DIRECT  Rs 50,000 -> Rs 62,000\n"
        "HDFC Flexi Cap Direct  regular  Invested Rs 80,000  Current Rs 95,000\n"
    )
    doc = parse_holdings_from_ocr_text(text)
    assert doc["source"]["engine"].startswith("nxance_ocr_layout")
    assert len(doc["lots"]) >= 1


def test_trained_bundle_predict():
    from app.intelligence.ml.trained import predict_all, load_bundle

    bundle = load_bundle()
    if not bundle:
        return  # skip if models not trained yet
    out = predict_all(
        {
            "portfolio_xirr": 11.0,
            "ter_waste_pct_aum": 0.8,
            "overlap_waste_pct_aum": 0.5,
            "hhi": 0.35,
            "equity_pct": 70,
            "regular_aum_pct": 40,
            "top_sector_pct": 25,
            "smallcap_pct": 15,
            "liquid_pct": 10,
            "est_tax_drag_pct_aum": 1.2,
            "n_lots": 6,
            "sip_regularity": 0.8,
            "elss_locked_pct": 5,
            "fd_pct": 10,
            "mean_holding_years": 3.0,
        }
    )
    assert out["available"] is True
    assert "has_ter_leak" in out["predictions"]


def test_allocation_l4():
    a = strategic_allocation(years=10, risk_bucket="balanced", required_return_pct=12)
    assert abs(sum(a["allocation_pct"].values()) - 100) < 1
    assert a["layer"] == "L4_optimize"


def test_health_pipeline():
    r = run_health_check(
        [
            {
                "name": "UTI Nifty 50",
                "current_value": 100000,
                "invested_amount": 80000,
                "plan_type": "direct",
                "asset_class": "mutual_fund",
            }
        ],
        {"goal": "Wealth", "target_amount": 500000, "years": 5, "monthly_sip": 5000, "risk": "moderate"},
        unlocked=False,
    )
    assert "intelligence_stack" in r
    assert "L1_quant" in r["intelligence_stack"]["layers"]
    assert r["unlocked"] is False


def test_construction_pipeline():
    r = run_construction(
        {
            "goal": "Retirement",
            "target_amount": 5_000_000,
            "years": 12,
            "monthly_sip": 15000,
            "lumpsum": 100000,
            "risk": "moderate",
        },
        unlocked=True,
    )
    assert r["engine"] == "construction"
    assert len(r["instruments"]) >= 2
    assert "L4_optimize" in r["intelligence_stack"]["layers"]


def test_construction_paywall():
    r = run_construction(
        {
            "goal": "Wealth",
            "target_amount": 2_000_000,
            "years": 8,
            "monthly_sip": 8000,
            "lumpsum": 50000,
            "risk": "conservative",
        },
        unlocked=False,
    )
    assert r["unlocked"] is False
    assert "paywall" in r


def test_number_guard_blocks_invented():
    payload = {"score": 72, "grade": "C", "issues": [{"title": "TER", "annual_cost_rs": 4200}]}
    bad = "Your score is 72 and you will earn 999999 percent guaranteed."
    g = number_guard(bad, payload)
    assert g["ok"] is False


def test_intent():
    assert intent_route("build me a portfolio") == "redirect_construction"
    assert intent_route("buy this stock now") == "refuse_execution"


def test_explain():
    report = {
        "engine": "health_check",
        "score": 62,
        "grade": "C",
        "total_value": 325000,
        "portfolio_xirr": 11.2,
        "issues": [{"title": "Overlap", "annual_cost_rs": 4800, "fix": "Switch one fund"}],
        "unlocked": True,
    }
    e = explain_report(report)
    assert e["number_guard_ok"] is True
    assert "62" in e["text"]


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  OK  {t.__name__}")
        except Exception as ex:
            failed += 1
            print(f"  FAIL {t.__name__}: {ex}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
