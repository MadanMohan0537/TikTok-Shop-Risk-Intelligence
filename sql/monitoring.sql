-- Daily marketplace risk telemetry for analyst dashboards.
SELECT
  substr(o.event_time, 1, 10) AS event_date,
  o.market,
  o.category,
  COUNT(*) AS order_count,
  ROUND(SUM(o.amount), 2) AS gmv,
  SUM(o.is_fraud) AS confirmed_fraud_orders,
  ROUND(100.0 * SUM(o.is_fraud) / COUNT(*), 2) AS fraud_rate_pct,
  SUM(CASE WHEN d.decision = 'BLOCK' THEN 1 ELSE 0 END) AS blocked_orders,
  SUM(CASE WHEN d.decision = 'MANUAL_REVIEW' THEN 1 ELSE 0 END) AS reviewed_orders
FROM orders o
JOIN risk_decisions d USING (order_id)
GROUP BY event_date, o.market, o.category
ORDER BY event_date DESC, gmv DESC;

