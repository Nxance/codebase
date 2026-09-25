#!/usr/bin/env python3
"""
L3 deep-style models (pure Python — no PyTorch required).

1) Fund embedding: multi-hot name/category → dense vector via trained projection
   (contrastive pairs from synthetic portfolios / name similarity).

2) Sequence model: NAV return window → risk/expected feature vector
   (small MLP on temporal stats; ready to swap real RNN later).

Outputs:
  training/models/fund_embedding_v1.json
  training/models/nav_sequence_v1.json
"""
from __future__ import annotations

import json
import math
import random
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
MODELS = ROOT / "training" / "models"
INDIA = ROOT / "data" / "india"
SYN = ROOT / "data" / "synthetic"
RNG = random.Random(7)
DIM = 32
VOCAB_SIZE = 512


def tokenize(name: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", name.lower()) if len(t) > 1]


def hash_token(t: str) -> int:
    return abs(hash(t)) % VOCAB_SIZE


def bow(name: str, category: str = "") -> list[float]:
    v = [0.0] * VOCAB_SIZE
    for t in tokenize(name) + tokenize(category):
        v[hash_token(t)] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def matvec(W: list[list[float]], x: list[float], b: list[float]) -> list[float]:
    out = []
    for i, row in enumerate(W):
        s = b[i] + sum(row[j] * x[j] for j in range(len(x)))
        out.append(s)
    return out


def l2norm(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def relu(v: list[float]) -> list[float]:
    return [max(0.0, x) for x in v]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def init_proj(in_dim: int, out_dim: int) -> tuple[list[list[float]], list[float]]:
    W = [[RNG.uniform(-0.05, 0.05) for _ in range(in_dim)] for _ in range(out_dim)]
    b = [0.0] * out_dim
    return W, b


def train_embeddings():
    """Contrastive: same-fund variants close; random pairs pushed apart."""
    names = []
    if (INDIA / "amfi_seed_funds.json").exists():
        seeds = json.loads((INDIA / "amfi_seed_funds.json").read_text())
        names = [(s.get("schemeName") or "", "mf") for s in seeds if s.get("schemeName")]
    # synthetic names
    for line in (SYN / "portfolios_train.jsonl").open() if (SYN / "portfolios_train.jsonl").exists() else []:
        try:
            doc = json.loads(line)
            for lot in doc.get("lots") or []:
                names.append((lot.get("name") or "", lot.get("asset_class") or ""))
        except Exception:
            continue
        if len(names) > 2000:
            break
    if not names:
        names = [
            ("UTI Nifty 50 Index Direct", "index"),
            ("Axis Bluechip Regular", "large"),
            ("HDFC Flexi Cap Direct", "flexi"),
        ]

    # unique
    seen = set()
    uniq = []
    for n, c in names:
        k = n.lower()
        if k and k not in seen:
            seen.add(k)
            uniq.append((n, c))
    names = uniq[:800]

    W, b = init_proj(VOCAB_SIZE, DIM)
    lr = 0.08
    epochs = 12
    for ep in range(epochs):
        loss_acc = 0.0
        steps = 0
        for i in range(min(400, len(names))):
            n1, c1 = names[RNG.randrange(len(names))]
            # positive: slightly perturbed name
            n_pos = n1.replace("Direct", "Dir").replace("Regular", "Reg")
            n_neg, c_neg = names[RNG.randrange(len(names))]
            while n_neg.lower() == n1.lower():
                n_neg, c_neg = names[RNG.randrange(len(names))]

            def embed(n, c):
                return l2norm(matvec(W, bow(n, c), b))

            e1, ep_, en = embed(n1, c1), embed(n_pos, c1), embed(n_neg, c_neg)
            # loss: maximize cos(e1,ep) minimize cos(e1,en)
            pos = cosine(e1, ep_)
            neg = cosine(e1, en)
            # gradient free finite-diff style updates on output space — simple delta rule
            # push e1 toward ep, away from en in W via feature correlation
            x1, xp, xn = bow(n1, c1), bow(n_pos, c1), bow(n_neg, c_neg)
            # target direction
            for d in range(DIM):
                err_pos = ep_[d] - e1[d]
                err_neg = -0.3 * en[d]
                delta = lr * (err_pos + err_neg)
                b[d] += delta * 0.1
                for j in range(VOCAB_SIZE):
                    if x1[j] != 0:
                        W[d][j] += delta * x1[j]
            loss_acc += (1 - pos) + max(0, neg)
            steps += 1
        if ep % 3 == 0:
            print(f"  embed epoch {ep} loss~{loss_acc/max(1,steps):.4f} names={len(names)}")

    bundle = {
        "version": "fund_embedding_v1",
        "type": "projection_bow",
        "dim": DIM,
        "vocab_size": VOCAB_SIZE,
        "W": W,
        "b": b,
        "layer": "L3_dl",
        "n_names_seen": len(names),
    }
    MODELS.mkdir(parents=True, exist_ok=True)
    (MODELS / "fund_embedding_v1.json").write_text(json.dumps(bundle))
    print("Saved fund_embedding_v1.json")
    return bundle


def fetch_nav_series(code: str, limit: int = 120) -> list[float]:
    try:
        with urllib.request.urlopen(f"https://api.mfapi.in/mf/{code}", timeout=12) as r:
            data = json.loads(r.read().decode())
        navs = [float(x["nav"]) for x in (data.get("data") or [])[:limit]]
        navs.reverse()  # oldest first
        return navs
    except Exception:
        return []


def sequence_features(navs: list[float]) -> list[float]:
    """Fixed-length temporal feature vector from NAV path."""
    if len(navs) < 5:
        return [0.0] * 16
    rets = []
    for i in range(1, len(navs)):
        if navs[i - 1] > 0:
            rets.append(navs[i] / navs[i - 1] - 1)
    if not rets:
        return [0.0] * 16
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    std = math.sqrt(var)
    # max drawdown
    peak = navs[0]
    mdd = 0.0
    for n in navs:
        peak = max(peak, n)
        if peak > 0:
            mdd = min(mdd, n / peak - 1)
    # last 5 returns pad
    last = rets[-5:] if len(rets) >= 5 else rets + [0] * (5 - len(rets))
    # simple momentum
    mom_20 = navs[-1] / navs[max(0, len(navs) - 20)] - 1 if len(navs) > 20 else 0
    mom_60 = navs[-1] / navs[max(0, len(navs) - 60)] - 1 if len(navs) > 60 else 0
    vol_ann = std * math.sqrt(252)
    return [
        mean * 252,
        vol_ann,
        mdd,
        mom_20,
        mom_60,
        min(rets),
        max(rets),
        last[0],
        last[1],
        last[2],
        last[3],
        last[4],
        len(rets) / 252,
        1.0 if mean > 0 else 0.0,
        abs(mean) / (std + 1e-6),
        (navs[-1] / navs[0] - 1) if navs[0] else 0,
    ]


def train_sequence():
    """MLP: sequence features → {expected_return_proxy, risk_score}."""
    codes = []
    if (INDIA / "amfi_seed_funds.json").exists():
        seeds = json.loads((INDIA / "amfi_seed_funds.json").read_text())
        codes = [str(s["schemeCode"]) for s in seeds[:25] if s.get("schemeCode")]
    # sample file
    samples = []
    for p in INDIA.glob("nav_history_sample_*.json"):
        try:
            hist = json.loads(p.read_text())
            navs = [float(x["nav"]) for x in reversed((hist.get("data") or [])[:120])]
            if len(navs) > 10:
                samples.append(navs)
        except Exception:
            pass
    for code in codes[:15]:
        navs = fetch_nav_series(code, 100)
        if len(navs) > 10:
            samples.append(navs)
    if len(samples) < 3:
        # synthetic GBM paths
        for _ in range(40):
            p = 100.0
            path = [p]
            for _d in range(80):
                p *= math.exp(RNG.gauss(0.0004, 0.01))
                path.append(p)
            samples.append(path)

    X = [sequence_features(s) for s in samples]
    # labels: realized ann return and vol from second half
    y_ret, y_risk = [], []
    for s in samples:
        mid = len(s) // 2
        if mid < 2:
            y_ret.append(0.1)
            y_risk.append(0.15)
            continue
        r = s[-1] / s[mid] - 1
        y_ret.append(max(-0.5, min(0.5, r)))
        rets = [s[i] / s[i - 1] - 1 for i in range(mid, len(s)) if s[i - 1] > 0]
        std = math.sqrt(sum(x * x for x in rets) / max(1, len(rets))) if rets else 0.1
        y_risk.append(min(0.5, std * math.sqrt(252)))

    in_dim = len(X[0])
    hidden = 24
    # 2-layer MLP
    W1 = [[RNG.uniform(-0.1, 0.1) for _ in range(in_dim)] for _ in range(hidden)]
    b1 = [0.0] * hidden
    W2 = [[RNG.uniform(-0.1, 0.1) for _ in range(hidden)] for _ in range(2)]
    b2 = [0.0, 0.0]
    lr = 0.02
    for ep in range(80):
        total = 0.0
        for i in range(len(X)):
            h = relu(matvec(W1, X[i], b1))
            out = matvec(W2, h, b2)
            err0 = out[0] - y_ret[i]
            err1 = out[1] - y_risk[i]
            total += err0 * err0 + err1 * err1
            # backprop output
            for k in range(hidden):
                W2[0][k] -= lr * err0 * h[k]
                W2[1][k] -= lr * err1 * h[k]
            b2[0] -= lr * err0
            b2[1] -= lr * err1
            # hidden
            for k in range(hidden):
                if h[k] <= 0:
                    continue
                grad = err0 * W2[0][k] + err1 * W2[1][k]
                b1[k] -= lr * grad
                for j in range(in_dim):
                    W1[k][j] -= lr * grad * X[i][j]
        if ep % 20 == 0:
            print(f"  seq epoch {ep} mse~{total/max(1,len(X)):.5f} n={len(X)}")

    bundle = {
        "version": "nav_sequence_v1",
        "type": "mlp_temporal_features",
        "in_dim": in_dim,
        "hidden": hidden,
        "W1": W1,
        "b1": b1,
        "W2": W2,
        "b2": b2,
        "layer": "L3_dl",
        "n_series": len(samples),
        "outputs": ["expected_return_proxy", "risk_score"],
    }
    (MODELS / "nav_sequence_v1.json").write_text(json.dumps(bundle))
    print("Saved nav_sequence_v1.json")
    return bundle


def main():
    print("=== L3 Fund embeddings ===")
    train_embeddings()
    print("=== L3 NAV sequence MLP ===")
    train_sequence()
    print("Done.")


if __name__ == "__main__":
    main()
