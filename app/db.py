import json
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.rules import score_order

DB_PATH = Path(__file__).resolve().parents[1] / "shopguard.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
  order_id TEXT PRIMARY KEY, buyer_id TEXT, seller_id TEXT, amount REAL,
  market TEXT, category TEXT, account_age_days INTEGER, device_id TEXT,
  device_account_count INTEGER, orders_last_hour INTEGER, promo_uses_24h INTEGER,
  home_state TEXT, transaction_state TEXT, distance_miles REAL,
  seller_refund_rate REAL, failed_payments INTEGER, event_time TEXT,
  is_fraud INTEGER, fraud_type TEXT
);
CREATE TABLE IF NOT EXISTS rule_hits (
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT, rule_id TEXT,
  rule_name TEXT, score INTEGER, severity TEXT, evidence TEXT
);
CREATE TABLE IF NOT EXISTS risk_decisions (
  order_id TEXT PRIMARY KEY, risk_score INTEGER, decision TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS cases (
  case_id TEXT PRIMARY KEY, order_id TEXT, priority TEXT, status TEXT,
  assigned_to TEXT, recommended_action TEXT, analyst_notes TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS enforcement_actions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, action TEXT,
  reason TEXT, actor TEXT, created_at TEXT
);
"""


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(seed: bool = True) -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        if seed and count == 0:
            seed_data(conn)


def seed_data(conn: sqlite3.Connection, count: int = 500, seed: int = 42) -> None:
    rng = random.Random(seed)
    markets = [("US", "CA", "NY", 2445), ("US", "TX", "FL", 1100),
               ("US", "WA", "WA", 18), ("US", "IL", "IL", 24)]
    categories = ["Beauty", "Electronics", "Fashion", "Home", "Collectibles"]
    fraud_types = ["promo_abuse", "account_takeover", "seller_collusion", "refund_abuse"]
    now = datetime.now(timezone.utc)
    for i in range(count):
        fraudulent = rng.random() < 0.14
        market, home, tx_state, distance = rng.choice(markets)
        if not fraudulent and rng.random() < 0.8:
            tx_state, distance = home, rng.randint(1, 80)
        order = {
            "order_id": f"ORD-{i+1:05d}", "buyer_id": f"BUY-{rng.randint(1, 280):04d}",
            "seller_id": f"SEL-{rng.randint(1, 55):03d}",
            "amount": round(rng.uniform(300, 1800) if fraudulent and rng.random() < .75 else rng.uniform(8, 500), 2),
            "market": market, "category": rng.choice(categories),
            "account_age_days": rng.randint(0, 8) if (fraudulent and rng.random() < .70) or (not fraudulent and rng.random() < .04) else rng.randint(7, 1200),
            "device_id": f"DEV-{rng.randint(1, 170):04d}",
            "device_account_count": rng.randint(5, 15) if (fraudulent and rng.random() < .72) or (not fraudulent and rng.random() < .03) else rng.randint(1, 4),
            "orders_last_hour": rng.randint(4, 10) if (fraudulent and rng.random() < .65) or (not fraudulent and rng.random() < .04) else rng.randint(0, 3),
            "promo_uses_24h": rng.randint(3, 8) if (fraudulent and rng.random() < .62) or (not fraudulent and rng.random() < .05) else rng.randint(0, 2),
            "home_state": home, "transaction_state": tx_state, "distance_miles": distance,
            "seller_refund_rate": rng.uniform(.30, .65) if (fraudulent and rng.random() < .58) or (not fraudulent and rng.random() < .03) else rng.uniform(.01, .20),
            "failed_payments": rng.randint(3, 7) if (fraudulent and rng.random() < .60) or (not fraudulent and rng.random() < .04) else rng.randint(0, 2),
            "event_time": (now - timedelta(minutes=rng.randint(0, 10080))).isoformat(),
            "is_fraud": int(fraudulent),
            "fraud_type": rng.choice(fraud_types) if fraudulent else "legitimate",
        }
        cols = ",".join(order)
        conn.execute(f"INSERT INTO orders ({cols}) VALUES ({','.join('?' for _ in order)})", tuple(order.values()))
        result = score_order(order)
        conn.execute("INSERT INTO risk_decisions VALUES (?, ?, ?, ?)",
                     (order["order_id"], result["risk_score"], result["decision"], now.isoformat()))
        for hit in result["rule_hits"]:
            conn.execute("INSERT INTO rule_hits(order_id,rule_id,rule_name,score,severity,evidence) VALUES(?,?,?,?,?,?)",
                         (order["order_id"], hit["rule_id"], hit["name"], hit["score"], hit["severity"], hit["evidence"]))
        if result["decision"] != "APPROVE":
            priority = "P0" if result["risk_score"] >= 80 else "P1" if result["risk_score"] >= 60 else "P2"
            conn.execute("INSERT INTO cases VALUES (?, ?, ?, 'OPEN', 'Unassigned', ?, '', ?)",
                         (f"CASE-{i+1:05d}", order["order_id"], priority, result["decision"], now.isoformat()))
    conn.commit()


def rows(query: str, params: tuple = ()) -> list[dict]:
    with connect() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]
