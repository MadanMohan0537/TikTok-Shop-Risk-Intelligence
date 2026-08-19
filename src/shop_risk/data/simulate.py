"""Deterministic synthetic TikTok Shop-style marketplace with labeled fraud cohorts.

The generator is built so the SQL feature marts and YAML rules in this repo
fire on injected abuse without drowning in false positives. It is interview
telemetry, not production traffic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from shop_risk.config import market_ids, market_weights

AS_OF = datetime(2026, 8, 18, 12, 0, 0)
WINDOW_DAYS = 28

COUPONS = ["NEWUSER", "LIVE15", "CREATOR10", "APP5", "FLASH20"]
REASONS = ["not_as_described", "damaged", "changed_mind", "missing_item", "sizing", "late"]
TEMPLATES = ["T_AMAZING", "T_FASTSHIP", "T_MUSTBUY", "T_LIVEHIT"]

# Approximate centroids so ATO geo-hops can be forced over the 800km rule.
MARKET_GEO: dict[str, tuple[float, float]] = {
    "US": (37.77, -122.42),
    "UK": (51.51, -0.13),
    "ID": (-6.20, 106.85),
    "TH": (13.76, 100.50),
    "VN": (10.82, 106.63),
    "MY": (3.14, 101.69),
    "PH": (14.60, 120.98),
}


@dataclass(frozen=True)
class Scale:
    n_buyers: int = 2400
    n_sellers: int = 360
    n_creators: int = 90
    n_orders: int = 7200
    n_refund_abusers: int = 36
    n_promo_abusers: int = 48
    n_brushing_sellers: int = 14
    n_review_farms: int = 10
    n_collusion_shops: int = 6
    n_ato: int = 42
    n_payfraud: int = 36
    n_affiliate_fraud: int = 8
    n_live_fraud: int = 8


TEST_SCALE = Scale(
    n_buyers=320,
    n_sellers=55,
    n_creators=22,
    n_orders=1100,
    n_refund_abusers=14,
    n_promo_abusers=16,
    n_brushing_sellers=6,
    n_review_farms=4,
    n_collusion_shops=6,
    n_ato=14,
    n_payfraud=14,
    n_affiliate_fraud=4,
    n_live_fraud=4,
)


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _pick_market(rng: np.random.Generator) -> str:
    ids = market_ids()
    weights = np.array(market_weights(), dtype=float)
    weights = weights / weights.sum()
    return str(rng.choice(ids, p=weights))


def _jitter_geo(rng: np.random.Generator, market: str, km: float = 40.0) -> tuple[float, float]:
    lat, lon = MARKET_GEO[market]
    # 1 deg lat ~ 111km
    dlat = rng.normal(0, km / 111.0)
    dlon = rng.normal(0, km / (111.0 * max(0.2, np.cos(np.radians(lat)))))
    return float(lat + dlat), float(lon + dlon)


def _far_geo(rng: np.random.Generator, home: tuple[float, float]) -> tuple[float, float]:
    # Force >= 800km hop used by ATO_GEO_DEVICE_VELOCITY.
    bearing = rng.uniform(0, 2 * np.pi)
    dist_km = rng.uniform(900, 2800)
    dlat = (dist_km * np.cos(bearing)) / 111.0
    dlon = (dist_km * np.sin(bearing)) / 111.0
    return float(home[0] + dlat), float(home[1] + dlon)


def _ts(rng: np.random.Generator, start: datetime, end: datetime) -> datetime:
    span = (end - start).total_seconds()
    return start + timedelta(seconds=float(rng.uniform(0, max(span, 1))))


def simulate(seed: int = 42, scale: Scale | None = None) -> dict[str, pd.DataFrame]:
    """Return a dict of warehouse tables, including ground-truth `labels`."""
    scale = scale or Scale()
    rng = _rng(seed)

    buyers = _buyers(rng, scale)
    sellers = _sellers(rng, scale)
    creators = _creators(rng, scale)
    instruments: list[dict[str, Any]] = []
    sessions: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    refunds: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    clicks: list[dict[str, Any]] = []
    lives: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []

    cursor = 0
    refund_buyers = buyers[cursor : cursor + scale.n_refund_abusers]
    cursor += scale.n_refund_abusers
    promo_buyers = buyers[cursor : cursor + scale.n_promo_abusers]
    cursor += scale.n_promo_abusers
    mule_n = max(scale.n_brushing_sellers * 24, 48)
    mule_buyers = buyers[cursor : cursor + mule_n]
    cursor += mule_n
    organic_buyers = buyers[cursor:]
    if len(organic_buyers) < 50:
        organic_buyers = buyers

    # Personal device + instrument per buyer.
    for b in buyers:
        instruments.append(
            {
                "instrument_id": f"I_{b['buyer_id']}",
                "buyer_id": b["buyer_id"],
                "created_at": b["created_at"] + timedelta(days=int(rng.integers(0, 14))),
            }
        )

    window_start = AS_OF - timedelta(days=WINDOW_DAYS)
    organic_n = scale.n_orders
    head = scale.n_brushing_sellers + scale.n_review_farms
    organic_sellers = sellers[head : max(head + 1, len(sellers) - scale.n_collusion_shops)]
    if not organic_sellers:
        organic_sellers = sellers
    home_seller = {
        b["buyer_id"]: organic_sellers[i % len(organic_sellers)] for i, b in enumerate(organic_buyers)
    }

    # --- organic baseline -------------------------------------------------
    for i in range(organic_n):
        buyer = organic_buyers[int(rng.integers(0, len(organic_buyers)))]
        seller = home_seller[buyer["buyer_id"]] if rng.random() < 0.9 else organic_sellers[int(rng.integers(0, len(organic_sellers)))]
        created = _ts(rng, window_start, AS_OF - timedelta(hours=8))
        delivered = created + timedelta(hours=float(rng.uniform(18, 90)))
        gmv = float(np.clip(rng.lognormal(3.4, 0.55), 8, 280))
        use_coupon = rng.random() < 0.18
        discount = gmv * float(rng.uniform(0.08, 0.22)) if use_coupon else 0.0
        creator_id = None
        honest_creators = creators[scale.n_affiliate_fraud :]
        if rng.random() < 0.22 and honest_creators:
            creator_id = honest_creators[int(rng.integers(0, len(honest_creators)))]["creator_id"]
        order = {
            "order_id": f"O{i:06d}",
            "buyer_id": buyer["buyer_id"],
            "seller_id": seller["seller_id"],
            "creator_id": creator_id,
            "market": buyer["market"],
            "created_at": created,
            "delivered_at": delivered,
            "gmv": round(gmv, 2),
            "discount_amount": round(discount, 2),
            "coupon_family": str(rng.choice(COUPONS)) if use_coupon else None,
            "device_id": buyer["device_id"],
            "ship_address_id": buyer["ship_address_id"],
            "ship_lat": buyer["home_lat"],
            "ship_lon": buyer["home_lon"],
            "instrument_id": f"I_{buyer['buyer_id']}",
            "avs_mismatch": 0,
            "bin_country_mismatch": 0,
            "auth_fail_1h": int(rng.integers(0, 2)),
        }
        orders.append(order)
        if rng.random() < 0.06 and delivered < AS_OF:
            refunds.append(_refund(rng, order, keep_item=False, hours=float(rng.uniform(48, 240))))
        if rng.random() < 0.28 and delivered < AS_OF:
            reviews.append(
                _review(
                    rng,
                    order,
                    rating=int(rng.integers(3, 6)),
                    delay_h=float(rng.uniform(24, 240)),
                    template=None,
                    verified=True,
                )
            )

    oid = organic_n

    # --- refund abuse -----------------------------------------------------
    for b in refund_buyers:
        labels.append({"entity_type": "buyer", "entity_id": b["buyer_id"], "typology": "refund_abuse"})
        n = int(rng.integers(5, 9))
        for _ in range(n):
            seller = organic_sellers[int(rng.integers(0, len(organic_sellers)))]
            created = _ts(rng, window_start, AS_OF - timedelta(days=2))
            delivered = created + timedelta(hours=float(rng.uniform(12, 48)))
            gmv = float(rng.uniform(25, 90))
            order = _base_order(oid, b, seller, created, delivered, gmv)
            oid += 1
            orders.append(order)
            refunds.append(
                _refund(
                    rng,
                    order,
                    keep_item=True,
                    hours=float(rng.uniform(4, 30)),
                    cycle=True,
                )
            )

    # --- promo stacking ---------------------------------------------------
    farm_devices = [f"D_PROMO_{k}" for k in range(6)]
    for idx, b in enumerate(promo_buyers):
        labels.append({"entity_type": "buyer", "entity_id": b["buyer_id"], "typology": "promo_abuse"})
        b["device_id"] = farm_devices[idx % len(farm_devices)]
        first = _ts(rng, window_start + timedelta(days=1), AS_OF - timedelta(days=3))
        b["created_at"] = first - timedelta(hours=float(rng.uniform(1, 10)))
        n = int(rng.integers(3, 5))
        families = list(rng.choice(COUPONS, size=3, replace=False))
        # Keep a farm device on a single shop so we don't look like a collusion ring.
        target = organic_sellers[idx % len(organic_sellers)]
        for j in range(n):
            created = first + timedelta(hours=float(j * rng.uniform(4, 18)))
            delivered = created + timedelta(hours=30)
            list_price = float(rng.uniform(30, 80))
            discount = list_price * float(rng.uniform(0.50, 0.70))
            gmv = list_price - discount
            order = _base_order(oid, b, target, created, delivered, gmv, discount=discount)
            order["coupon_family"] = families[j % len(families)]
            order["device_id"] = b["device_id"]
            oid += 1
            orders.append(order)

    # --- brushing sellers -------------------------------------------------
    brush_sellers = sellers[: scale.n_brushing_sellers]
    mule_i = 0
    seeded_mules: set[str] = set()
    for s in brush_sellers:
        labels.append({"entity_type": "seller", "entity_id": s["seller_id"], "typology": "brushing"})
        n = int(rng.integers(16, 24))
        for _ in range(n):
            mule = mule_buyers[mule_i % len(mule_buyers)]
            mule_i += 1
            created_ord = _ts(rng, AS_OF - timedelta(days=20), AS_OF - timedelta(hours=6))
            if mule["buyer_id"] not in seeded_mules:
                mule["created_at"] = created_ord - timedelta(hours=float(rng.uniform(2, 36)))
                seeded_mules.add(mule["buyer_id"])
            delivered = created_ord + timedelta(hours=20)
            gmv = float(rng.uniform(12, 35))
            order = _base_order(oid, mule, s, created_ord, delivered, gmv)
            oid += 1
            orders.append(order)
            reviews.append(
                _review(
                    rng,
                    order,
                    rating=5,
                    delay_h=float(rng.uniform(0.2, 1.8)),
                    template=str(rng.choice(TEMPLATES)) if rng.random() < 0.4 else None,
                    verified=True,
                )
            )

    # --- review farms -----------------------------------------------------
    farm_sellers = sellers[scale.n_brushing_sellers : scale.n_brushing_sellers + scale.n_review_farms]
    burst_day = AS_OF.date() - timedelta(days=3)
    burst_start = datetime(burst_day.year, burst_day.month, burst_day.day, 9, 0, 0)
    for s in farm_sellers:
        labels.append(
            {"entity_type": "seller", "entity_id": s["seller_id"], "typology": "review_manipulation"}
        )
        n = int(rng.integers(22, 32))
        for k in range(n):
            buyer = organic_buyers[int(rng.integers(0, len(organic_buyers)))]
            created = burst_start + timedelta(minutes=float(k * rng.uniform(8, 20)))
            delivered = created - timedelta(days=2)
            gmv = float(rng.uniform(15, 40))
            # Backdate the order so the review is not a 2h-after-order brushing clone.
            order_created = created - timedelta(days=float(rng.uniform(3, 10)))
            order = _base_order(oid, buyer, s, order_created, delivered, gmv)
            oid += 1
            orders.append(order)
            reviews.append(
                _review(
                    rng,
                    order,
                    rating=5,
                    delay_h=None,
                    at=created,
                    template=str(rng.choice(TEMPLATES)),
                    verified=False,
                )
            )

    # --- collusion / mule shops -------------------------------------------
    collude = sellers[-(scale.n_collusion_shops) :]
    shared_payout = "PO_RING_01"
    shared_devices = [f"D_RING_{k}" for k in range(3)]
    for s in collude:
        s["payout_id"] = shared_payout
        labels.append(
            {"entity_type": "seller", "entity_id": s["seller_id"], "typology": "seller_collusion"}
        )
        for _ in range(int(rng.integers(4, 7))):
            buyer = buyers[int(rng.integers(0, len(buyers)))]
            created = _ts(rng, window_start, AS_OF - timedelta(days=1))
            delivered = created + timedelta(hours=36)
            order = _base_order(oid, buyer, s, created, delivered, float(rng.uniform(18, 55)))
            order["device_id"] = str(rng.choice(shared_devices))
            oid += 1
            orders.append(order)

    # --- ATO on trusted accounts ------------------------------------------
    established = [b for b in organic_buyers if (AS_OF - b["created_at"]).days >= 90]
    if len(established) < scale.n_ato:
        established = organic_buyers
    for k in range(scale.n_ato):
        victim = established[k % len(established)]
        victim["created_at"] = AS_OF - timedelta(days=int(rng.integers(90, 400)))
        # Seed a trusted history order on the home device.
        hist_t = AS_OF - timedelta(days=int(rng.integers(10, 25)))
        seller = sellers[int(rng.integers(0, len(sellers)))]
        hist = _base_order(oid, victim, seller, hist_t, hist_t + timedelta(days=2), float(rng.uniform(20, 60)))
        oid += 1
        orders.append(hist)
        new_device = f"D_ATO_{k}"
        far_lat, far_lon = _far_geo(rng, (victim["home_lat"], victim["home_lon"]))
        ship_id = f"SHIP_ATO_{k}"
        t0 = _ts(rng, AS_OF - timedelta(days=5), AS_OF - timedelta(hours=4))
        # Probe on the home device so the takeover order has velocity_1h >= 2
        # while still looking like a brand-new device.
        probe_seller = organic_sellers[int(rng.integers(0, len(organic_sellers)))]
        probe = _base_order(
            oid, victim, probe_seller, t0, t0 + timedelta(days=3), float(rng.uniform(15, 40))
        )
        oid += 1
        orders.append(probe)
        created = t0 + timedelta(minutes=12)
        seller = organic_sellers[int(rng.integers(0, len(organic_sellers)))]
        gmv = float(rng.uniform(95, 240))
        order = _base_order(oid, victim, seller, created, created + timedelta(days=3), gmv)
        order["device_id"] = new_device
        order["ship_address_id"] = ship_id
        order["ship_lat"] = far_lat
        order["ship_lon"] = far_lon
        oid += 1
        orders.append(order)
        labels.append({"entity_type": "order", "entity_id": order["order_id"], "typology": "ato"})

    # --- payment / stolen instrument --------------------------------------
    pay_buyers = established[scale.n_ato : scale.n_ato + scale.n_payfraud]
    if len(pay_buyers) < scale.n_payfraud:
        pay_buyers = organic_buyers[: scale.n_payfraud]
    for k, b in enumerate(pay_buyers[: scale.n_payfraud]):
        labels.append({"entity_type": "order", "entity_id": f"O{oid:06d}", "typology": "payment_fraud"})
        inst_id = f"I_NEW_{k}"
        created = _ts(rng, AS_OF - timedelta(days=4), AS_OF - timedelta(hours=2))
        instruments.append(
            {
                "instrument_id": inst_id,
                "buyer_id": b["buyer_id"],
                "created_at": created - timedelta(minutes=float(rng.uniform(20, 150))),
            }
        )
        seller = sellers[int(rng.integers(0, len(sellers)))]
        order = _base_order(
            oid, b, seller, created, created + timedelta(days=2), float(rng.uniform(60, 180))
        )
        order["instrument_id"] = inst_id
        order["avs_mismatch"] = 1
        order["bin_country_mismatch"] = int(rng.random() < 0.7)
        order["auth_fail_1h"] = int(rng.integers(4, 8))
        oid += 1
        orders.append(order)

    # --- affiliate / creator self-loop ------------------------------------
    aff_creators = creators[: scale.n_affiliate_fraud]
    click_id = 0
    for c in aff_creators:
        labels.append(
            {"entity_type": "creator", "entity_id": c["creator_id"], "typology": "affiliate_fraud"}
        )
        farm_dev = f"D_AFF_{c['creator_id']}"
        sessions.append(
            {
                "session_id": f"SESS_{c['creator_id']}",
                "actor_type": "creator",
                "actor_id": c["creator_id"],
                "device_id": farm_dev,
                "created_at": AS_OF - timedelta(days=20),
            }
        )
        n_ord = int(rng.integers(10, 16))
        shop = organic_sellers[int(rng.integers(0, len(organic_sellers)))]
        for j in range(n_ord):
            buyer = organic_buyers[int(rng.integers(0, len(organic_buyers)))]
            created = _ts(rng, window_start, AS_OF - timedelta(hours=12))
            order = _base_order(
                oid, buyer, shop, created, created + timedelta(hours=40), float(rng.uniform(18, 70))
            )
            order["creator_id"] = c["creator_id"]
            order["device_id"] = farm_dev  # same device as creator session → self-purchase
            oid += 1
            orders.append(order)
        # Click farm: few devices, high volume relative to orders.
        for _ in range(n_ord * 32):
            clicks.append(
                {
                    "click_id": f"CL{click_id:07d}",
                    "creator_id": c["creator_id"],
                    "device_id": farm_dev if rng.random() < 0.85 else f"D_AFF_OTHER_{rng.integers(0, 3)}",
                    "buyer_id": buyers[int(rng.integers(0, len(buyers)))]["buyer_id"],
                    "created_at": _ts(rng, window_start, AS_OF),
                }
            )
            click_id += 1

    # organic clicks so honest creators have low HHI / reasonable CTR
    honest = creators[scale.n_affiliate_fraud :]
    for c in honest:
        for _ in range(int(rng.integers(20, 60))):
            clicks.append(
                {
                    "click_id": f"CL{click_id:07d}",
                    "creator_id": c["creator_id"],
                    "device_id": f"D_CLK_{rng.integers(0, 80)}",
                    "buyer_id": buyers[int(rng.integers(0, len(buyers)))]["buyer_id"],
                    "created_at": _ts(rng, window_start, AS_OF),
                }
            )
            click_id += 1

    # --- livestream fraud -------------------------------------------------
    live_creators = creators[scale.n_affiliate_fraud : scale.n_affiliate_fraud + scale.n_live_fraud]
    for c in live_creators:
        labels.append(
            {"entity_type": "creator", "entity_id": c["creator_id"], "typology": "livestream_fraud"}
        )
        lives.append(
            {
                "livestream_id": f"LV_{c['creator_id']}",
                "creator_id": c["creator_id"],
                "viewer_spike_z": float(rng.uniform(3.8, 7.5)),
                "gifts_gmv": float(rng.uniform(400, 1800)),
                "unique_gifters": int(rng.integers(8, 25)),
                "featured_brush_overlap": float(rng.uniform(0.35, 0.8)),
            }
        )
    for c in creators:
        if c["creator_id"] in {x["creator_id"] for x in live_creators}:
            continue
        lives.append(
            {
                "livestream_id": f"LV_{c['creator_id']}",
                "creator_id": c["creator_id"],
                "viewer_spike_z": float(abs(rng.normal(0.4, 0.7))),
                "gifts_gmv": float(rng.uniform(20, 220)),
                "unique_gifters": int(rng.integers(15, 80)),
                "featured_brush_overlap": float(max(0.0, rng.normal(0.05, 0.04))),
            }
        )

    frames = {
        "buyers": pd.DataFrame(buyers),
        "sellers": pd.DataFrame(sellers),
        "creators": pd.DataFrame(creators),
        "instruments": pd.DataFrame(instruments),
        "sessions": pd.DataFrame(sessions),
        "orders": pd.DataFrame(orders),
        "refunds": pd.DataFrame(refunds),
        "reviews": pd.DataFrame(reviews),
        "affiliate_clicks": pd.DataFrame(clicks),
        "livestreams": pd.DataFrame(lives),
        "labels": pd.DataFrame(labels),
    }
    return frames


def _buyers(rng: np.random.Generator, scale: Scale) -> list[dict[str, Any]]:
    rows = []
    for i in range(scale.n_buyers):
        market = _pick_market(rng)
        lat, lon = _jitter_geo(rng, market)
        age_days = int(rng.integers(5, 420))
        created = AS_OF - timedelta(days=age_days, hours=int(rng.integers(0, 23)))
        rows.append(
            {
                "buyer_id": f"B{i:06d}",
                "market": market,
                "created_at": created,
                "home_lat": lat,
                "home_lon": lon,
                "device_id": f"D_B{i:06d}",
                "ship_address_id": f"SHIP_B{i:06d}",
            }
        )
    return rows


def _sellers(rng: np.random.Generator, scale: Scale) -> list[dict[str, Any]]:
    rows = []
    for i in range(scale.n_sellers):
        market = _pick_market(rng)
        rows.append(
            {
                "seller_id": f"S{i:05d}",
                "market": market,
                "payout_id": f"PO{i:05d}",
                "warehouse_id": f"WH{int(rng.integers(0, 80)):03d}",
            }
        )
    return rows


def _creators(rng: np.random.Generator, scale: Scale) -> list[dict[str, Any]]:
    rows = []
    for i in range(scale.n_creators):
        rows.append(
            {
                "creator_id": f"C{i:04d}",
                "market": _pick_market(rng),
                "followers": int(rng.integers(800, 250_000)),
            }
        )
    return rows


def _base_order(
    oid: int,
    buyer: dict[str, Any],
    seller: dict[str, Any],
    created: datetime,
    delivered: datetime,
    gmv: float,
    discount: float = 0.0,
) -> dict[str, Any]:
    return {
        "order_id": f"O{oid:06d}",
        "buyer_id": buyer["buyer_id"],
        "seller_id": seller["seller_id"],
        "creator_id": None,
        "market": buyer["market"],
        "created_at": created,
        "delivered_at": delivered,
        "gmv": round(gmv, 2),
        "discount_amount": round(discount, 2),
        "coupon_family": None,
        "device_id": buyer["device_id"],
        "ship_address_id": buyer["ship_address_id"],
        "ship_lat": buyer["home_lat"],
        "ship_lon": buyer["home_lon"],
        "instrument_id": f"I_{buyer['buyer_id']}",
        "avs_mismatch": 0,
        "bin_country_mismatch": 0,
        "auth_fail_1h": 0,
    }


def _refund(
    rng: np.random.Generator,
    order: dict[str, Any],
    *,
    keep_item: bool,
    hours: float,
    cycle: bool = False,
) -> dict[str, Any]:
    requested = order["delivered_at"] + timedelta(hours=hours)
    reason = str(rng.choice(REASONS)) if cycle else str(rng.choice(REASONS[:3]))
    return {
        "refund_id": f"R_{order['order_id']}",
        "order_id": order["order_id"],
        "buyer_id": order["buyer_id"],
        "seller_id": order["seller_id"],
        "requested_at": requested,
        "amount": order["gmv"],
        "keep_item": keep_item,
        "reason_code": reason,
    }


def _review(
    rng: np.random.Generator,
    order: dict[str, Any],
    *,
    rating: int,
    delay_h: float | None,
    template: str | None,
    verified: bool,
    at: datetime | None = None,
) -> dict[str, Any]:
    created = at if at is not None else order["created_at"] + timedelta(hours=float(delay_h or 48))
    return {
        "review_id": f"RV_{order['order_id']}",
        "order_id": order["order_id"],
        "seller_id": order["seller_id"],
        "rating": rating,
        "created_at": created,
        "template_id": template,
        "verified": verified,
    }
