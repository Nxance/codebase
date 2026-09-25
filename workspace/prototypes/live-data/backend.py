"""
Nxance Live Health Check — Backend (Single File)
=================================================
Real AMFI live NAV data + Real XIRR + Real Jaccard Overlap

Run locally:
    pip install fastapi uvicorn requests scipy numpy pandas openpyxl python-multipart
    python main.py

Deploy on Railway:
    1. Push this file to GitHub
    2. Connect repo on railway.app
    3. Done — live URL milega
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import requests, math, io, os
from datetime import date, datetime
from scipy.optimize import brentq
import pandas as pd

app = FastAPI(title="Nxance Health Check API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── CACHE (avoid hitting AMFI too often) ──────────────────────────
_cache: dict = {}
_cache_ts: dict = {}
CACHE_HOURS = 6

def cache_fresh(key):
    if key not in _cache_ts: return False
    return (datetime.now() - _cache_ts[key]).seconds < CACHE_HOURS * 3600

# ── LIVE AMFI DATA ────────────────────────────────────────────────
def amfi_fund(scheme_code: str) -> dict:
    """Fetch full fund data (NAV history + meta) from mfapi.in"""
    key = f"fund_{scheme_code}"
    if cache_fresh(key): return _cache[key]
    try:
        r = requests.get(f"https://api.mfapi.in/mf/{scheme_code}", timeout=10)
        if r.status_code == 200:
            data = r.json()
            _cache[key] = data
            _cache_ts[key] = datetime.now()
            return data
    except Exception as e:
        print(f"AMFI error for {scheme_code}: {e}")
    return {}

def amfi_search(query: str) -> list:
    """Search funds by name"""
    try:
        r = requests.get("https://api.mfapi.in/mf/search", params={"q": query}, timeout=8)
        if r.status_code == 200:
            return r.json()[:10]
    except: pass
    return []

def get_live_nav(scheme_code: str) -> float | None:
    data = amfi_fund(scheme_code)
    navs = data.get("data", [])
    if navs:
        return float(navs[0]["nav"])
    return None

def get_nav_on_date(scheme_code: str, target_date: date) -> float | None:
    """Get NAV closest to (but not after) target date"""
    data = amfi_fund(scheme_code)
    navs = data.get("data", [])
    for entry in reversed(navs):  # oldest first
        try:
            d = datetime.strptime(entry["date"], "%d-%m-%Y").date()
            if d <= target_date:
                return float(entry["nav"])
        except: continue
    return None

# ── XIRR ─────────────────────────────────────────────────────────
def xirr_calc(cash_flows: list, dates: list) -> float | None:
    if len(cash_flows) < 2: return None
    d0 = dates[0]
    t = [(d - d0).days / 365.25 for d in dates]
    def npv(r):
        return sum(cf / (1 + r) ** ti for cf, ti in zip(cash_flows, t))
    try:
        result = brentq(npv, -0.9999, 10.0, maxiter=1000, xtol=1e-6)
        return round(result * 100, 2)
    except:
        return None

def holding_xirr(invested, current_value, purchase_date_str, units=None, scheme_code=None):
    """Calculate XIRR — uses live NAV if scheme_code provided"""
    result = {"xirr": None, "current_value": current_value, "nav_live": False,
              "current_nav": None, "purchase_nav": None}

    try:
        pdate = datetime.strptime(purchase_date_str[:10], "%Y-%m-%d").date()
    except:
        pdate = date(2021, 1, 1)

    # Try live NAV calculation
    if scheme_code and units:
        current_nav = get_live_nav(scheme_code)
        purchase_nav = get_nav_on_date(scheme_code, pdate)
        if current_nav and purchase_nav and purchase_nav > 0:
            cv = round(units * current_nav, 2)
            ai = round(units * purchase_nav, 2)
            result.update({
                "current_value": cv,
                "current_nav": current_nav,
                "purchase_nav": purchase_nav,
                "nav_live": True,
            })
            result["xirr"] = xirr_calc([-ai, cv], [pdate, date.today()])
            return result

    # Fallback: use provided values
    if invested > 0 and current_value > 0:
        result["xirr"] = xirr_calc([-invested, current_value], [pdate, date.today()])

    return result

# ── TER DATABASE (source: AMFI monthly disclosures May 2026) ─────
TER = {
    "regular": {
        "default": 1.55,
        "axis bluechip": 1.54, "mirae large cap": 1.52, "mirae asset large": 1.52,
        "sbi blue chip": 1.62, "hdfc flexi cap": 1.68, "hdfc top 100": 1.68,
        "parag parikh": 1.71, "kotak emerging": 1.89, "icici pru bluechip": 1.56,
        "aditya birla": 1.87, "nifty 50 index": 0.20, "uti nifty": 0.18,
        "nippon india": 1.78, "axis midcap": 1.88, "sbi small cap": 1.73,
        "hdfc midcap": 1.72, "kotak flexicap": 1.62, "franklin india": 1.78,
    },
    "direct": {
        "default": 0.50,
        "axis bluechip": 0.47, "mirae large cap": 0.52, "mirae asset large": 0.52,
        "sbi blue chip": 0.83, "hdfc flexi cap": 0.98, "hdfc top 100": 0.98,
        "parag parikh": 0.66, "kotak emerging": 0.55, "icici pru bluechip": 0.98,
        "aditya birla": 0.96, "nifty 50 index": 0.10, "uti nifty": 0.10,
        "nippon india": 0.78, "axis midcap": 0.55, "sbi small cap": 0.70,
        "hdfc midcap": 0.72, "kotak flexicap": 0.62, "franklin india": 0.78,
    },
}

def get_ter(name: str, plan: str) -> float:
    n = name.lower()
    db = TER.get(plan, TER["regular"])
    for key, val in db.items():
        if key != "default" and key in n:
            return val
    return db["default"]

# ── OVERLAP (Jaccard) — AMFI top-30 holdings May 2026 ──────────
HOLDINGS_DB = {
    "axis bluechip":      ["HDFC Bank","Infosys","Reliance","ICICI Bank","TCS","Kotak MB","Bajaj Finance","HUL","Asian Paints","Maruti","Titan","L&T","Nestle","Sun Pharma","Wipro","HCL Tech","Bajaj Auto","Pidilite","Mphasis","Persistent","Berger Paints","Abbott India","Whirlpool","Marico","Britannia","Godrej Consumer","Tata Consumer","Crompton","Divi's Lab","Avenue Supermarts"],
    "mirae large cap":    ["HDFC Bank","Infosys","Reliance","ICICI Bank","TCS","Kotak MB","Axis Bank","L&T","Bharti Airtel","ITC","HCL Tech","Bajaj Finance","SBI","HUL","Asian Paints","Maruti","Sun Pharma","Titan","Ultratech","M&M","Power Grid","NTPC","Tata Motors","Wipro","Bajaj Auto","Eicher Motors","Tata Steel","JSW Steel","Cipla","Dr Reddy"],
    "mirae asset large":  ["HDFC Bank","Infosys","Reliance","ICICI Bank","TCS","Kotak MB","Axis Bank","L&T","Bharti Airtel","ITC","HCL Tech","Bajaj Finance","SBI","HUL","Asian Paints","Maruti","Sun Pharma","Titan","Ultratech","M&M","Power Grid","NTPC","Tata Motors","Wipro","Bajaj Auto","Eicher Motors","Tata Steel","JSW Steel","Cipla","Dr Reddy"],
    "sbi blue chip":      ["HDFC Bank","Infosys","ICICI Bank","Reliance","TCS","L&T","Kotak MB","Axis Bank","HUL","ITC","Bajaj Finance","Sun Pharma","Asian Paints","Maruti","Titan","HCL Tech","Bharti Airtel","Nestle","SBI","Tata Motors","M&M","Power Grid","Ultratech","NTPC","Bajaj Auto","Eicher Motors","Wipro","Tech Mahindra","Tata Steel","Adani Enterprises"],
    "hdfc flexi cap":     ["HDFC Bank","ICICI Bank","Infosys","Reliance","Axis Bank","Bharti Airtel","SBI","ITC","Kotak MB","L&T","Bajaj Finance","Sun Pharma","HCL Tech","TCS","Maruti","Asian Paints","HUL","Titan","M&M","Power Grid","NTPC","Coal India","ONGC","Tata Motors","Ultratech","Adani Ports","Divi's Lab","Cipla","Dr Reddy","Godrej Consumer"],
    "hdfc top 100":       ["HDFC Bank","Infosys","Reliance","ICICI Bank","TCS","Axis Bank","L&T","Kotak MB","HUL","Bharti Airtel","ITC","SBI","Bajaj Finance","Sun Pharma","Asian Paints","Maruti","HCL Tech","Titan","M&M","NTPC","Power Grid","Ultratech","Wipro","ONGC","Coal India","BPCL","Bajaj Auto","Eicher Motors","Tech Mahindra","Tata Steel"],
    "icici pru bluechip": ["HDFC Bank","Infosys","Reliance","ICICI Bank","TCS","L&T","Kotak MB","HUL","Axis Bank","ITC","Sun Pharma","Asian Paints","Bajaj Finance","Maruti","Wipro","SBI","HCL Tech","Bharti Airtel","Nestle","NTPC","Titan","M&M","Power Grid","Ultratech","Bajaj Auto","Eicher Motors","Divi's Lab","Cipla","Tech Mahindra","Tata Consumer"],
    "parag parikh flexi": ["HDFC Bank","Infosys","ITC","Axis Bank","HCL Tech","Coal India","Bajaj Holdings","Power Grid","Maruti","HUL","ICICI Bank","Microsoft","Alphabet","Amazon","Meta","Berkshire","ONGC","BPCL","SAIL","Indian Hotels","Persistent","Mphasis","Bajaj Auto","Hero MotoCorp","NMDC","GMDC","Zydus Life","Sun TV","Dr Reddy","Cipla"],
    "kotak emerging":     ["Persistent","Coforge","KEC Intl","Carborundum","Kajaria","Safari Ind","Affle","Dixon Tech","Techno Elec","Mold-Tek","Sona BLW","Aavas Fin","KPIT Tech","CG Power","Greaves Cotton","Blue Star","Polycab","KEI Ind","Lemon Tree","Chalet Hotels","Fine Org","CAMS","Metropolis","Vijaya Diag","Redington","Radico","Tata Elxsi","Minda Industries","Astral","Prince Pipes"],
    "axis midcap":        ["Persistent","Coforge","Mphasis","KPIT Tech","Dixon Tech","Voltas","PI Ind","Alkem Lab","Cholamandalam","Trent","BSE","Cummins","Supreme Ind","Crompton","Thermax","Kajaria","V-Mart","Kalpataru","Emami","AIA Eng","Astral","Prince Pipes","Laurus Labs","Divi's Lab","Natco Pharma","Ipca Lab","Eris Life","Ajanta Pharma","JB Chem","Granules"],
    "sbi small cap":      ["Blue Star","Techno Elec","Finolex Cables","KEI Ind","Lemon Tree","Chalet Hotels","Safari Ind","Greaves Cotton","CAMS","Metropolis","Vijaya Diag","Redington","Radico","Prince Pipes","Astral","Minda Ind","GNE Cables","Polycab","Bajaj Elec","Havells","Crompton","Voltas","Whirlpool","NOCIL","Sudarshan Chem","BASF","Navin Fluorine","Atul Ltd","Fine Org","Vinati Org"],
    "nifty 50 index":     ["HDFC Bank","Infosys","Reliance","ICICI Bank","TCS","Kotak MB","HUL","Axis Bank","L&T","Bajaj Finance","Bharti Airtel","Asian Paints","Maruti","Titan","HCL Tech","Sun Pharma","ITC","M&M","Ultratech","NTPC","Power Grid","Bajaj Auto","Eicher Motors","Wipro","Tech Mahindra","Divi's Lab","SBI Life","HDFC Life","Tata Steel","Adani Enterprises"],
    "uti nifty":          ["HDFC Bank","Infosys","Reliance","ICICI Bank","TCS","Kotak MB","HUL","Axis Bank","L&T","Bajaj Finance","Bharti Airtel","Asian Paints","Maruti","Titan","HCL Tech","Sun Pharma","ITC","M&M","Ultratech","NTPC","Power Grid","Bajaj Auto","Eicher Motors","Wipro","Tech Mahindra","Divi's Lab","SBI Life","HDFC Life","Tata Steel","Adani Enterprises"],
    "hdfc midcap":        ["Cholamandalam","Persistent","Supreme Ind","Cummins","Voltas","BSE","Trent","PI Ind","KPIT Tech","Dixon Tech","Thermax","Kajaria","Emami","Crompton","AIA Eng","Redington","Coforge","Mphasis","V-Mart","Kalpataru","Astral","Prince Pipes","Laurus Labs","Natco","Ipca","Eris Life","Ajanta","JB Chem","Granules","Balkrishna Ind"],
    "kotak flexicap":     ["HDFC Bank","Infosys","Reliance","ICICI Bank","Axis Bank","L&T","TCS","Kotak MB","Bharti Airtel","ITC","HUL","Bajaj Finance","SBI","Asian Paints","Maruti","Sun Pharma","HCL Tech","Titan","M&M","NTPC","Power Grid","Ultratech","Wipro","ONGC","Coal India","Bajaj Auto","Eicher Motors","Tech Mahindra","Tata Steel","Adani Ports"],
}

def fund_key(name: str) -> str | None:
    n = name.lower()
    for key in HOLDINGS_DB:
        if key in n or all(w in n for w in key.split() if len(w) > 3):
            return key
    return None

def jaccard(a: list, b: list) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb: return 0.0
    return len(sa & sb) / len(sa | sb)

# ── BENCHMARKS (NSE 5-year CAGR, as of Jun 2026) ─────────────────
BENCH = {
    "Nifty 50":           14.5,
    "Nifty 500":          15.2,
    "Category Avg MF":    12.8,
    "SBI FD (5yr)":        7.1,
}

# ── MODELS ────────────────────────────────────────────────────────
class Holding(BaseModel):
    name: str
    scheme_code: Optional[str] = None
    current_value: float
    invested_amount: float
    units: Optional[float] = None
    plan_type: str = "regular"
    purchase_date: str = "2021-01-01"
    asset_class: str = "mutual_fund"

class Goal(BaseModel):
    name: str = "Goal"
    target_amount: float
    target_year: int

class AnalyseReq(BaseModel):
    holdings: list[Holding]
    goals: list[Goal] = []

# ── MAIN ENDPOINT ─────────────────────────────────────────────────
@app.post("/api/analyse")
async def analyse(req: AnalyseReq):
    if not req.holdings:
        raise HTTPException(400, "No holdings provided")

    h_results = []
    total_val   = 0
    total_inv   = 0
    xirr_num    = 0  # weighted numerator
    xirr_den    = 0  # weighted denominator

    for h in req.holdings:
        xd = holding_xirr(h.invested_amount, h.current_value,
                          h.purchase_date, h.units, h.scheme_code)
        cv = xd["current_value"]
        total_val += cv
        total_inv += h.invested_amount
        if xd["xirr"] is not None:
            xirr_num += xd["xirr"] * cv
            xirr_den += cv

        ter_val = get_ter(h.name, h.plan_type)
        ret_pct = round((cv - h.invested_amount) / h.invested_amount * 100, 2) if h.invested_amount > 0 else 0

        h_results.append({
            "name":          h.name,
            "scheme_code":   h.scheme_code,
            "current_value": round(cv, 2),
            "invested":      h.invested_amount,
            "return_pct":    ret_pct,
            "xirr":          xd["xirr"],
            "plan_type":     h.plan_type,
            "ter":           ter_val,
            "current_nav":   xd.get("current_nav"),
            "purchase_nav":  xd.get("purchase_nav"),
            "nav_live":      xd.get("nav_live", False),
            "asset_class":   h.asset_class,
        })

    port_xirr   = round(xirr_num / xirr_den, 2) if xirr_den > 0 else None
    total_ret   = round((total_val - total_inv) / total_inv * 100, 2) if total_inv > 0 else 0

    # Benchmarks
    bench_out = {}
    if port_xirr:
        for bname, bval in BENCH.items():
            bench_out[bname] = {
                "return": bval,
                "difference": round(port_xirr - bval, 2),
                "verdict": "Outperforming ✓" if port_xirr > bval else "Underperforming ✗"
            }

    # TER waste
    ter_waste = 0
    ter_detail = []
    for r, h in zip(h_results, req.holdings):
        if h.plan_type == "regular" and h.asset_class == "mutual_fund":
            dir_ter = get_ter(h.name, "direct")
            waste   = round(r["current_value"] * (r["ter"] - dir_ter) / 100, 2)
            if waste > 0:
                ter_waste += waste
                ter_detail.append({
                    "fund": h.name,
                    "regular_ter": r["ter"],
                    "direct_ter": dir_ter,
                    "annual_waste_rs": waste,
                })

    # Overlap
    mf_pairs   = [(r, h) for r, h in zip(h_results, req.holdings) if h.asset_class == "mutual_fund"]
    ovlp_pairs = []
    ovlp_waste = 0
    for i in range(len(mf_pairs)):
        for j in range(i+1, len(mf_pairs)):
            ri, hi = mf_pairs[i]; rj, hj = mf_pairs[j]
            ki = fund_key(hi.name); kj = fund_key(hj.name)
            if not ki or not kj: continue
            jac = jaccard(HOLDINGS_DB[ki], HOLDINGS_DB[kj])
            if jac > 0.15:
                smaller = min(ri["current_value"], rj["current_value"])
                waste   = round(smaller * jac * 0.008, 2)
                ovlp_waste += waste
                ovlp_pairs.append({
                    "fund_a": hi.name, "fund_b": hj.name,
                    "overlap_pct": round(jac * 100, 1),
                    "annual_waste_rs": waste,
                    "severity": "high" if jac > 0.5 else "medium" if jac > 0.3 else "low",
                    "common_stocks": sorted(set(HOLDINGS_DB[ki]) & set(HOLDINGS_DB[kj]))[:8],
                })
    ovlp_pairs.sort(key=lambda x: x["overlap_pct"], reverse=True)

    # Goals
    goal_results = []
    for g in req.goals:
        yrs = g.target_year - date.today().year
        if yrs <= 0: continue
        projected = total_val * (1.12 ** yrs)
        prob = min(90, max(5, int((projected / g.target_amount) * 55)))
        shortfall = max(0, g.target_amount - projected)
        extra_sip = round(shortfall / (yrs * 12) / 500) * 500 if shortfall > 0 else 0
        goal_results.append({
            "goal": g.name, "target_amount": g.target_amount, "target_year": g.target_year,
            "success_probability": prob, "projected_value": round(projected),
            "shortfall_rs": round(shortfall), "extra_sip_needed": extra_sip,
            "verdict": "On track ✓" if prob >= 70 else "Behind — action needed" if prob >= 40 else "Off track ✗",
        })

    # Health Score
    score = 100
    if port_xirr is not None:
        if port_xirr < 6: score -= 25
        elif port_xirr < 10: score -= 15
        elif port_xirr < 12: score -= 5
        if port_xirr > 15: score += 3

    ter_pct = ter_waste / total_val * 100 if total_val > 0 else 0
    if ter_pct > 1.0: score -= 20
    elif ter_pct > 0.5: score -= 12
    elif ter_pct > 0.2: score -= 6

    ovp_pct = ovlp_waste / total_val * 100 if total_val > 0 else 0
    if ovp_pct > 0.8: score -= 15
    elif ovp_pct > 0.4: score -= 8
    elif ovp_pct > 0.1: score -= 4

    for g in goal_results:
        if g["success_probability"] < 30: score -= 15
        elif g["success_probability"] < 50: score -= 8
        elif g["success_probability"] < 70: score -= 4

    score = max(15, min(98, score))
    if score >= 86: grade, glabel = "A", "Excellent"
    elif score >= 71: grade, glabel = "B", "Good"
    elif score >= 56: grade, glabel = "C", "Fair"
    elif score >= 41: grade, glabel = "D", "Poor"
    else: grade, glabel = "F", "Critical"

    # Issues
    issues = []
    if ter_waste > 0:
        issues.append({
            "title": "Regular Plan Cost Leak",
            "annual_cost_rs": ter_waste,
            "severity": "high" if ter_waste > 3000 else "medium",
            "description": f"{len(ter_detail)} fund(s) in Regular plan — identical to Direct but ₹{ter_waste:,.0f}/yr more expensive.",
            "fix": "Switch to Direct plan on MF Central (mfcentral.com). Free, 3–5 working days.",
            "detail": ter_detail,
        })
    if ovlp_waste > 0 and ovlp_pairs:
        w = ovlp_pairs[0]
        issues.append({
            "title": "Fund Overlap Detected",
            "annual_cost_rs": ovlp_waste,
            "severity": "high" if w["overlap_pct"] > 50 else "medium",
            "description": f"Worst pair: {w['fund_a']} vs {w['fund_b']} — {w['overlap_pct']}% same stocks. Double TER on identical holdings.",
            "fix": "Replace one overlapping large-cap fund with a different category (mid-cap, international, or debt fund).",
            "detail": ovlp_pairs,
        })
    if port_xirr is not None and port_xirr < 10:
        beats = sum(1 for b in bench_out.values() if b["difference"] > 0)
        issues.append({
            "title": "Below-Benchmark Returns",
            "annual_cost_rs": round(total_val * 0.025),
            "severity": "high" if port_xirr < 7 else "medium",
            "description": f"XIRR: {port_xirr}%/yr. Beats {beats}/{len(BENCH)} benchmarks. Nifty 50 delivered {BENCH['Nifty 50']}%/yr.",
            "fix": "Review consistently underperforming funds. Consider adding Nifty 50 index fund (TER 0.10–0.20%).",
            "detail": bench_out,
        })
    for g in goal_results:
        if g["success_probability"] < 70:
            issues.append({
                "title": f"Goal at Risk: {g['goal']}",
                "annual_cost_rs": g["extra_sip_needed"] * 12,
                "severity": "high" if g["success_probability"] < 30 else "medium",
                "description": f"Only {g['success_probability']}% probability of reaching ₹{g['target_amount']:,.0f} by {g['target_year']}.",
                "fix": f"Increase monthly SIP by ₹{g['extra_sip_needed']:,.0f} to improve probability.",
                "detail": g,
            })

    issues.sort(key=lambda x: x["annual_cost_rs"], reverse=True)
    for i, iss in enumerate(issues):
        iss["rank"] = i + 1
        iss["is_free"] = (i == 0)

    # NxanceLM summary
    top = issues[0] if issues else None
    summary = (f"Your portfolio scored {score}/100 (Grade {grade} — {glabel}). "
               f"Value: ₹{total_val:,.0f} · Return: {total_ret}%"
               + (f" · XIRR: {port_xirr}%/yr" if port_xirr else "") + ". ")
    if top:
        summary += f"Biggest issue: {top['title']} — costs ₹{top['annual_cost_rs']:,.0f}/year. "
        total_avoidable = ter_waste + ovlp_waste
        if total_avoidable > 0:
            summary += f"Fix Regular plans + overlap → save ₹{total_avoidable:,.0f}/year immediately."
    else:
        summary += "No major issues detected — portfolio looks healthy. Keep up the SIPs."

    live_count = sum(1 for r in h_results if r.get("nav_live"))

    return {
        "score": score, "grade": grade, "grade_label": glabel,
        "total_value": round(total_val, 2), "total_invested": round(total_inv, 2),
        "total_return_pct": total_ret, "portfolio_xirr": port_xirr,
        "ter_waste_annual_rs": round(ter_waste, 2),
        "overlap_waste_annual_rs": round(ovlp_waste, 2),
        "benchmark_comparison": bench_out,
        "issues": issues[:5],
        "holdings_detail": h_results,
        "goal_results": goal_results,
        "summary": summary,
        "data_source": f"Live AMFI NAV (mfapi.in) — {live_count}/{len(h_results)} holdings with live NAV",
    }

# ── EXCEL PARSE ───────────────────────────────────────────────────
@app.post("/api/parse-excel")
async def parse_excel(file: UploadFile = File(...)):
    content = await file.read()
    buf = io.BytesIO(content)
    try:
        df = pd.read_csv(buf) if file.filename.endswith(".csv") else pd.read_excel(buf)
    except Exception as e:
        raise HTTPException(400, f"Cannot read file: {e}")

    df.columns = [c.strip().lower().replace(" ","_").replace("-","_") for c in df.columns]
    rows = []
    for _, r in df.iterrows():
        name = str(r.get("fund_name") or r.get("fund") or r.get("name") or "").strip()
        if not name: continue
        try:
            val  = float(str(r.get("current_value") or r.get("value") or 0).replace(",","").replace("₹",""))
            inv  = float(str(r.get("invested_amount") or r.get("invested") or val).replace(",","").replace("₹",""))
            plan = "direct" if "direct" in str(r.get("plan_type") or r.get("plan") or "regular").lower() else "regular"
            pdate = str(r.get("purchase_date") or r.get("date") or "2021-01-01")[:10]
            units = r.get("units"); units = float(units) if units and str(units) != "nan" else None
            scheme = str(r.get("scheme_code") or r.get("amfi_code") or "").strip() or None
        except: continue
        if val > 0:
            rows.append({"name": name, "scheme_code": scheme, "current_value": val,
                         "invested_amount": inv, "units": units, "plan_type": plan,
                         "purchase_date": pdate, "asset_class": "mutual_fund"})
    if not rows:
        raise HTTPException(400, "No valid rows found. Check column names match template.")
    return {"holdings": rows, "count": len(rows)}

# ── FUND SEARCH ───────────────────────────────────────────────────
@app.get("/api/search")
async def search(q: str):
    results = amfi_search(q)
    return {"results": [{"scheme_code": str(r.get("schemeCode","")),
                         "name": r.get("schemeName","")} for r in results]}

@app.get("/")
async def root():
    return {"status": "ok", "app": "Nxance Health Check", "data": "Live AMFI via mfapi.in"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
