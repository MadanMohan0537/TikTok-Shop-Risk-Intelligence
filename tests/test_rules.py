from shop_risk.rules.engine import hits_frame
from shop_risk.rules.evaluate import evaluate, threshold_curve


def test_every_typology_has_a_hit(hits):
    found = {h.typology for h in hits}
    expected = {
        "refund_abuse",
        "brushing",
        "promo_abuse",
        "review_manipulation",
        "seller_collusion",
        "ato",
        "payment_fraud",
        "affiliate_fraud",
        "livestream_fraud",
    }
    missing = expected - found
    assert not missing, f"rules did not fire for {missing}"


def test_hits_are_scored(hits):
    assert hits
    frame = hits_frame(hits)
    assert frame["score"].between(0, 1.0001).all()
    assert set(frame["severity"]).issubset({"low", "medium", "high", "critical"})


def test_precision_recall_are_interview_credible(con, hits):
    ev = evaluate(con, hits)
    assert ev.overall_precision >= 0.75
    assert ev.overall_recall >= 0.55
    assert ev.true_positives >= 20
    # No typology should be a complete miss on the injected holdout.
    for row in ev.by_typology:
        assert row.recall >= 0.4, row


def test_policy_curve_monotone_enforced(con, hits):
    curve = threshold_curve(con, hits)
    enforced = list(curve["enforced"])
    assert enforced == sorted(enforced, reverse=True)
