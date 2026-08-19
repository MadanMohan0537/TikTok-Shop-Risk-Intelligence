-- Buyer-level 28d risk features for refund, promo, and ATO precursors.
CREATE OR REPLACE TABLE buyer_features AS
WITH first_order AS (
  SELECT buyer_id, MIN(created_at) AS first_order_at
  FROM orders
  GROUP BY 1
),
order_agg AS (
  SELECT
    o.buyer_id,
    COUNT(*) AS orders_28d,
    SUM(o.gmv) AS gmv_28d,
    AVG(o.gmv) AS aov,
    SUM(o.discount_amount) / NULLIF(SUM(o.gmv + o.discount_amount), 0) AS discount_ratio,
    COUNT(DISTINCT o.coupon_family) FILTER (WHERE o.coupon_family IS NOT NULL) AS coupon_family_n,
    COUNT(DISTINCT o.device_id) AS devices_n,
    COUNT(DISTINCT o.market) AS markets_n,
    COUNT(DISTINCT o.ship_address_id) AS ship_addresses_n
  FROM orders o
  GROUP BY 1
),
refund_agg AS (
  SELECT
    r.buyer_id,
    COUNT(*) AS refunds_28d,
    AVG(CASE WHEN r.keep_item THEN 1.0 ELSE 0.0 END) AS keep_item_share,
    MEDIAN(date_diff('hour', o.delivered_at, r.requested_at)) AS median_hours_to_refund,
    COUNT(DISTINCT r.reason_code) AS reason_code_n
  FROM refunds r
  JOIN orders o USING (order_id)
  GROUP BY 1
),
new_account_device AS (
  SELECT
    o.buyer_id,
    COUNT(DISTINCT o2.buyer_id) AS device_linked_new_accounts
  FROM orders o
  JOIN buyers b ON b.buyer_id = o.buyer_id
  JOIN orders o2 ON o2.device_id = o.device_id AND o2.buyer_id <> o.buyer_id
  JOIN buyers b2 ON b2.buyer_id = o2.buyer_id
  WHERE date_diff('hour', b2.created_at, o2.created_at) <= 48
  GROUP BY 1
)
SELECT
  b.buyer_id,
  b.market,
  b.created_at AS buyer_created_at,
  COALESCE(oa.orders_28d, 0) AS orders_28d,
  COALESCE(oa.gmv_28d, 0) AS gmv_28d,
  COALESCE(oa.aov, 0) AS aov,
  COALESCE(oa.discount_ratio, 0) AS discount_ratio,
  COALESCE(oa.coupon_family_n, 0) AS coupon_family_n,
  COALESCE(oa.devices_n, 0) AS devices_n,
  COALESCE(oa.markets_n, 0) AS markets_n,
  COALESCE(ra.refunds_28d, 0) AS refunds_28d,
  CASE WHEN COALESCE(oa.orders_28d, 0) = 0 THEN 0
       ELSE COALESCE(ra.refunds_28d, 0)::DOUBLE / oa.orders_28d
  END AS refund_rate_28d,
  COALESCE(ra.keep_item_share, 0) AS keep_item_share,
  COALESCE(ra.median_hours_to_refund, 999) AS median_hours_to_refund,
  COALESCE(ra.reason_code_n, 0) AS reason_code_n,
  COALESCE(date_diff('hour', b.created_at, fo.first_order_at), 9999) AS account_age_hours_at_first_order,
  COALESCE(nad.device_linked_new_accounts, 0) AS device_linked_new_accounts
FROM buyers b
LEFT JOIN order_agg oa USING (buyer_id)
LEFT JOIN refund_agg ra USING (buyer_id)
LEFT JOIN first_order fo USING (buyer_id)
LEFT JOIN new_account_device nad USING (buyer_id);
