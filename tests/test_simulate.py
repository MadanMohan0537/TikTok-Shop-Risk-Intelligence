from shop_risk.data.simulate import TEST_SCALE, simulate


def test_simulate_is_deterministic():
    a = simulate(seed=3, scale=TEST_SCALE)
    b = simulate(seed=3, scale=TEST_SCALE)
    assert list(a.keys()) == list(b.keys())
    assert len(a["orders"]) == len(b["orders"])
    assert a["orders"]["gmv"].sum() == b["orders"]["gmv"].sum()
    assert set(a["labels"]["typology"]) >= {
        "refund_abuse",
        "brushing",
        "ato",
        "payment_fraud",
        "affiliate_fraud",
        "livestream_fraud",
        "seller_collusion",
        "promo_abuse",
        "review_manipulation",
    }


def test_feature_marts_exist(con):
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    for name in (
        "buyer_features",
        "seller_features",
        "creator_features",
        "order_features",
        "market_kpis",
        "daily_market_orders",
    ):
        assert name in tables
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        assert n > 0
