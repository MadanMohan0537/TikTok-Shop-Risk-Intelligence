from app.db import rows


def overview() -> dict:
    summary = rows("""
      SELECT COUNT(*) orders, ROUND(SUM(amount),2) gmv,
        SUM(is_fraud) confirmed_fraud,
        ROUND(100.0*SUM(is_fraud)/COUNT(*),2) fraud_rate,
        SUM(CASE WHEN d.decision='BLOCK' THEN 1 ELSE 0 END) blocked,
        SUM(CASE WHEN d.decision='MANUAL_REVIEW' THEN 1 ELSE 0 END) reviewed,
        SUM(CASE WHEN d.decision='APPROVE' AND o.is_fraud=0 THEN 1 ELSE 0 END) legitimate_approved
      FROM orders o JOIN risk_decisions d USING(order_id)
    """)[0]
    summary["open_cases"] = rows("SELECT COUNT(*) n FROM cases WHERE status='OPEN'")[0]["n"]
    return summary


def trends() -> list[dict]:
    return rows("""
      SELECT substr(event_time,1,10) day, COUNT(*) orders,
        SUM(is_fraud) fraud_orders, ROUND(SUM(amount),2) gmv
      FROM orders GROUP BY day ORDER BY day
    """)


def top_rules() -> list[dict]:
    return rows("""
      SELECT rule_id, rule_name, COUNT(*) hits, ROUND(AVG(score),1) avg_score
      FROM rule_hits GROUP BY rule_id, rule_name ORDER BY hits DESC
    """)


def cases(limit: int = 100) -> list[dict]:
    return rows("""
      SELECT c.*, o.buyer_id, o.seller_id, o.amount, o.fraud_type,
        d.risk_score, d.decision
      FROM cases c JOIN orders o USING(order_id) JOIN risk_decisions d USING(order_id)
      ORDER BY d.risk_score DESC, c.created_at DESC LIMIT ?
    """, (limit,))


def ring_candidates() -> list[dict]:
    return rows("""
      SELECT device_id, COUNT(DISTINCT buyer_id) buyers,
        COUNT(DISTINCT seller_id) sellers, COUNT(*) orders,
        ROUND(SUM(amount),2) total_value, SUM(is_fraud) fraud_orders
      FROM orders GROUP BY device_id
      HAVING COUNT(DISTINCT buyer_id)>=3
      ORDER BY fraud_orders DESC, total_value DESC LIMIT 25
    """)


def simulate_policy(min_score: int) -> dict:
    return rows("""
      SELECT ? threshold, COUNT(*) affected_orders,
        SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END) fraud_captured,
        SUM(CASE WHEN is_fraud=0 THEN 1 ELSE 0 END) false_positives,
        ROUND(SUM(CASE WHEN is_fraud=1 THEN amount ELSE 0 END),2) fraud_value_captured,
        ROUND(100.0*SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) precision,
        ROUND(100.0*SUM(CASE WHEN is_fraud=1 THEN 1 ELSE 0 END)/
          NULLIF((SELECT SUM(is_fraud) FROM orders),0),2) recall
      FROM orders o JOIN risk_decisions d USING(order_id) WHERE d.risk_score>=?
    """, (min_score, min_score))[0]
