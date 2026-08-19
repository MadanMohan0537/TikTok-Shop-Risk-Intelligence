from app.rules import decision, score_order


def base_order():
    return {"amount": 50, "account_age_days": 365, "device_account_count": 1,
            "orders_last_hour": 1, "promo_uses_24h": 0, "home_state": "CA",
            "transaction_state": "CA", "distance_miles": 10,
            "seller_refund_rate": .05, "failed_payments": 0}


def test_legitimate_order_is_approved():
    result = score_order(base_order())
    assert result["risk_score"] == 0
    assert result["decision"] == "APPROVE"


def test_coordinated_abuse_is_blocked_and_explainable():
    order = base_order()
    order.update(amount=900, account_age_days=2, device_account_count=8,
                 orders_last_hour=6, promo_uses_24h=5, failed_payments=4)
    result = score_order(order)
    assert result["decision"] == "BLOCK"
    assert len(result["rule_hits"]) >= 4
    assert all("evidence" in hit for hit in result["rule_hits"])


def test_decision_thresholds():
    assert decision(39) == "APPROVE"
    assert decision(40) == "MANUAL_REVIEW"
    assert decision(70) == "BLOCK"

