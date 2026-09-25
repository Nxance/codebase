"""SQLite persistence — users, sessions, reports, unlocks, funnel events. ₹0."""
from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "nxance_mbp.db"

# Demo unlock codes (zero payment gateway). Replace/add real codes after UPI.
VALID_UNLOCK_CODES = {
    "DEMO-UNLOCK",
    "NXANCE-TEST",
    "NXANCE-PAID",  # issue manually after user pays UPI
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = connect()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT,
            phone TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT,
            unlocked INTEGER DEFAULT 0,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            engine TEXT,
            payload TEXT,
            unlocked INTEGER DEFAULT 0,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            event TEXT,
            meta TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS unlocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            code TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS payments (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            amount_inr REAL,
            method TEXT,
            status TEXT,
            unlock_code TEXT,
            meta TEXT,
            created_at TEXT,
            confirmed_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def new_id() -> str:
    return secrets.token_hex(8)


def create_user(name: str, phone: str) -> dict:
    uid = new_id()
    token = secrets.token_urlsafe(24)
    now = datetime.utcnow().isoformat()
    conn = connect()
    conn.execute(
        "INSERT INTO users (id, name, phone, created_at) VALUES (?,?,?,?)",
        (uid, name, phone, now),
    )
    conn.execute(
        "INSERT INTO sessions (token, user_id, unlocked, created_at) VALUES (?,?,0,?)",
        (token, uid, now),
    )
    conn.commit()
    conn.close()
    log_event(uid, "signup", {"phone": phone})
    return {
        "user_id": uid,
        "token": token,
        "name": name,
        "phone": phone,
        "unlocked": False,
    }


def get_session(token: str) -> Optional[dict]:
    if not token:
        return None
    conn = connect()
    row = conn.execute(
        "SELECT s.token, s.user_id, s.unlocked, u.name, u.phone FROM sessions s "
        "JOIN users u ON u.id = s.user_id WHERE s.token = ?",
        (token,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def create_payment(
    user_id: str,
    *,
    amount_inr: float = 99.0,
    method: str = "dummy_upi",
) -> dict:
    """Dummy payment order — no real gateway. Status starts as pending."""
    pid = "pay_" + new_id()
    now = datetime.utcnow().isoformat()
    conn = connect()
    conn.execute(
        "INSERT INTO payments (id, user_id, amount_inr, method, status, unlock_code, meta, created_at, confirmed_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            pid,
            user_id,
            amount_inr,
            method,
            "pending",
            None,
            json.dumps({"note": "dummy_gateway"}),
            now,
            None,
        ),
    )
    conn.commit()
    conn.close()
    log_event(user_id, "payment_created", {"payment_id": pid, "amount": amount_inr})
    return {
        "payment_id": pid,
        "amount_inr": amount_inr,
        "method": method,
        "status": "pending",
        "upi_vpa_demo": "nxance@okaxis",
        "qr_note": "Demo only — no real UPI charge. Tap Confirm payment in app.",
        "created_at": now,
    }


def confirm_payment(payment_id: str, user_id: str) -> Optional[dict]:
    """Mark dummy payment paid and issue unlock code + unlock session."""
    conn = connect()
    row = conn.execute(
        "SELECT * FROM payments WHERE id = ? AND user_id = ?",
        (payment_id, user_id),
    ).fetchone()
    if not row:
        conn.close()
        return None
    now = datetime.utcnow().isoformat()
    code = "NXANCE-PAID"
    conn.execute(
        "UPDATE payments SET status=?, unlock_code=?, confirmed_at=? WHERE id=?",
        ("paid", code, now, payment_id),
    )
    conn.execute(
        "UPDATE sessions SET unlocked=1 WHERE user_id=?",
        (user_id,),
    )
    conn.execute(
        "INSERT INTO unlocks (user_id, code, created_at) VALUES (?,?,?)",
        (user_id, code, now),
    )
    conn.commit()
    conn.close()
    log_event(user_id, "payment_confirmed", {"payment_id": payment_id, "code": code})
    return {
        "payment_id": payment_id,
        "status": "paid",
        "unlock_code": code,
        "unlocked": True,
        "confirmed_at": now,
        "message": "Dummy payment success. Full intelligence unlocked.",
    }


def get_payment(payment_id: str, user_id: str) -> Optional[dict]:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM payments WHERE id = ? AND user_id = ?",
        (payment_id, user_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def set_unlocked(user_id: str, code: str) -> bool:
    code_u = code.strip().upper()
    if code_u not in VALID_UNLOCK_CODES:
        return False
    conn = connect()
    conn.execute(
        "UPDATE sessions SET unlocked = 1 WHERE user_id = ?", (user_id,)
    )
    conn.execute(
        "INSERT INTO unlocks (user_id, code, created_at) VALUES (?,?,?)",
        (user_id, code_u, datetime.utcnow().isoformat()),
    )
    # Mark recent reports unlocked
    conn.execute(
        "UPDATE reports SET unlocked = 1 WHERE user_id = ?", (user_id,)
    )
    conn.commit()
    conn.close()
    log_event(user_id, "paid", {"code": code_u})
    return True


def save_report(user_id: str, engine: str, payload: dict, unlocked: bool) -> str:
    rid = new_id()
    conn = connect()
    conn.execute(
        "INSERT INTO reports (id, user_id, engine, payload, unlocked, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (
            rid,
            user_id,
            engine,
            json.dumps(payload, default=str),
            1 if unlocked else 0,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    log_event(user_id, "report_created", {"engine": engine, "report_id": rid})
    return rid


def get_report(report_id: str, user_id: str) -> Optional[dict]:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM reports WHERE id = ? AND user_id = ?",
        (report_id, user_id),
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["payload"] = json.loads(d["payload"])
    return d


def log_event(user_id: Optional[str], event: str, meta: Optional[dict] = None) -> None:
    conn = connect()
    conn.execute(
        "INSERT INTO events (user_id, event, meta, created_at) VALUES (?,?,?,?)",
        (
            user_id,
            event,
            json.dumps(meta or {}),
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def funnel_stats() -> dict[str, Any]:
    conn = connect()
    rows = conn.execute(
        "SELECT event, COUNT(*) as c FROM events GROUP BY event"
    ).fetchall()
    users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    paid = conn.execute(
        "SELECT COUNT(DISTINCT user_id) as c FROM unlocks"
    ).fetchone()["c"]
    conn.close()
    return {
        "users": users,
        "paid_users": paid,
        "events": {r["event"]: r["c"] for r in rows},
    }
