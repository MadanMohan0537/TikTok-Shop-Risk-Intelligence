from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    name: str
    score: int
    severity: str
    evidence: str
    recommended_action: str


def evaluate_order(order: dict[str, Any]) -> list[dict[str, Any]]:
    """Return transparent, versioned rule hits for one marketplace order."""
    hits: list[RuleHit] = []

    def add(rule_id: str, name: str, score: int, severity: str,
            evidence: str, action: str = "MANUAL_REVIEW") -> None:
        hits.append(RuleHit(rule_id, name, score, severity, evidence, action))

    if order["account_age_days"] < 7 and order["amount"] >= 300:
        add("NEW_ACCOUNT_HIGH_VALUE_V1", "New account, high-value order", 30, "high",
            f"Account is {order['account_age_days']} days old; order is ${order['amount']:.2f}")
    if order["device_account_count"] >= 5:
        add("SHARED_DEVICE_V1", "Device shared by many accounts", 25, "high",
            f"Device is linked to {order['device_account_count']} buyer accounts")
    if order["orders_last_hour"] >= 4:
        add("ORDER_VELOCITY_V1", "Rapid order velocity", 20, "medium",
            f"Buyer placed {order['orders_last_hour']} orders in one hour")
    if order["promo_uses_24h"] >= 3 and order["account_age_days"] < 30:
        add("PROMO_ABUSE_V1", "Possible promotion abuse", 20, "medium",
            f"Promotion used {order['promo_uses_24h']} times by a new account")
    if order["home_state"] != order["transaction_state"] and order["distance_miles"] >= 500:
        add("LOCATION_MISMATCH_V1", "Location anomaly", 15, "medium",
            f"{order['home_state']} to {order['transaction_state']}, {order['distance_miles']:.0f} miles")
    if order["seller_refund_rate"] >= 0.30:
        add("SELLER_REFUND_SPIKE_V1", "Seller refund-rate spike", 25, "high",
            f"Seller refund rate is {order['seller_refund_rate']:.1%}", "HOLD_SELLER_PAYOUT")
    if order["failed_payments"] >= 3:
        add("PAYMENT_RETRY_V1", "Repeated payment failures", 20, "high",
            f"{order['failed_payments']} failed payments before checkout")

    return [asdict(hit) for hit in hits]


def decision(score: int) -> str:
    if score >= 70:
        return "BLOCK"
    if score >= 40:
        return "MANUAL_REVIEW"
    return "APPROVE"


def score_order(order: dict[str, Any]) -> dict[str, Any]:
    hits = evaluate_order(order)
    score = min(100, sum(hit["score"] for hit in hits))
    return {"risk_score": score, "decision": decision(score), "rule_hits": hits}

