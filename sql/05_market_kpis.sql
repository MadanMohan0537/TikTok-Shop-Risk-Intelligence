-- Market telemetry: volume, GMV-at-risk proxies, and mix shifts.
CREATE OR REPLACE TABLE market_kpis AS
WITH order_m AS (
  SELECT
    market,
    COUNT(*) AS orders_n,
    SUM(gmv) AS gmv,
    AVG(gmv) AS aov,
    AVG(discount_amount / NULLIF(gmv + discount_amount, 0)) AS avg_discount_ratio
  FROM orders
  GROUP BY 1
),
refund_m AS (
  SELECT
    o.market,
    COUNT(*) AS refunds_n,
    SUM(r.amount) AS refund_gmv
  FROM refunds r
  JOIN orders o USING (order_id)
  GROUP BY 1
),
seller_m AS (
  SELECT market, COUNT(*) AS sellers_n FROM sellers GROUP BY 1
),
buyer_m AS (
  SELECT market, COUNT(*) AS buyers_n FROM buyers GROUP BY 1
)
SELECT
  om.market,
  bm.buyers_n,
  sm.sellers_n,
  om.orders_n,
  om.gmv,
  om.aov,
  om.avg_discount_ratio,
  COALESCE(rm.refunds_n, 0) AS refunds_n,
  COALESCE(rm.refund_gmv, 0) AS refund_gmv,
  CASE WHEN om.orders_n = 0 THEN 0
       ELSE COALESCE(rm.refunds_n, 0)::DOUBLE / om.orders_n
  END AS refund_rate,
  CASE WHEN om.gmv = 0 THEN 0
       ELSE COALESCE(rm.refund_gmv, 0) / om.gmv
  END AS refund_gmv_ratio
FROM order_m om
LEFT JOIN refund_m rm USING (market)
LEFT JOIN seller_m sm USING (market)
LEFT JOIN buyer_m bm USING (market)
ORDER BY om.gmv DESC;

CREATE OR REPLACE TABLE daily_market_orders AS
SELECT
  market,
  CAST(created_at AS DATE) AS dt,
  COUNT(*) AS orders_n,
  SUM(gmv) AS gmv,
  AVG(discount_amount / NULLIF(gmv + discount_amount, 0)) AS discount_ratio
FROM orders
GROUP BY 1, 2
ORDER BY 2, 1;
