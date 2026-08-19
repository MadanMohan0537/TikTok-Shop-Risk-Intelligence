-- Seller-level 28d features for brushing, review manipulation, and collusion hops.
CREATE OR REPLACE TABLE seller_features AS
WITH order_agg AS (
  SELECT
    o.seller_id,
    COUNT(*) AS orders_28d,
    SUM(o.gmv) AS gmv_28d,
    COUNT(DISTINCT o.buyer_id) AS unique_buyers,
    AVG(CASE WHEN date_diff('hour', b.created_at, o.created_at) <= 48 THEN 1.0 ELSE 0.0 END) AS new_buyer_share,
    COUNT(DISTINCT o.device_id) AS devices_n
  FROM orders o
  JOIN buyers b USING (buyer_id)
  GROUP BY 1
),
refund_agg AS (
  SELECT seller_id, COUNT(*) AS refunds_28d
  FROM refunds
  GROUP BY 1
),
review_agg AS (
  SELECT
    seller_id,
    COUNT(*) AS reviews_n,
    AVG(rating) AS avg_rating,
    AVG(CASE WHEN template_id IS NOT NULL THEN 1.0 ELSE 0.0 END) AS template_review_share,
    AVG(CASE WHEN verified THEN 1.0 ELSE 0.0 END) AS verified_share,
    1 - AVG(CASE WHEN verified THEN 1.0 ELSE 0.0 END) AS unverified_review_share
  FROM reviews
  GROUP BY 1
),
review_join AS (
  SELECT
    r.seller_id,
    AVG(CASE WHEN date_diff('hour', o.created_at, r.created_at) <= 2 THEN 1.0 ELSE 0.0 END) AS review_within_2h_share
  FROM reviews r
  JOIN orders o USING (order_id)
  GROUP BY 1
),
review_burst AS (
  SELECT seller_id, MAX(cnt) AS review_velocity_24h
  FROM (
    SELECT seller_id, date_trunc('day', created_at) AS d, COUNT(*) AS cnt
    FROM reviews
    GROUP BY 1, 2
  )
  GROUP BY 1
),
shared_device AS (
  SELECT
    a.seller_id,
    COUNT(DISTINCT b.seller_id) AS shared_device_peers
  FROM orders a
  JOIN (
    SELECT device_id
    FROM orders
    GROUP BY 1
    HAVING COUNT(DISTINCT seller_id) >= 3
       AND COUNT(DISTINCT buyer_id) >= 2
  ) mule USING (device_id)
  JOIN orders b ON a.device_id = b.device_id AND a.seller_id <> b.seller_id
  GROUP BY 1
),
shared_payout AS (
  SELECT
    s.seller_id,
    COUNT(DISTINCT s2.seller_id) AS shared_payout_peers
  FROM sellers s
  JOIN sellers s2 ON s.payout_id = s2.payout_id AND s.seller_id <> s2.seller_id
  GROUP BY 1
),
device_share_on_orders AS (
  SELECT
    o.seller_id,
    AVG(CASE WHEN peer.peers > 0 THEN 1.0 ELSE 0.0 END) AS shared_device_order_share
  FROM orders o
  LEFT JOIN (
    SELECT device_id, COUNT(DISTINCT seller_id) - 1 AS peers
    FROM orders
    GROUP BY 1
  ) peer USING (device_id)
  GROUP BY 1
)
SELECT
  s.seller_id,
  s.market,
  s.payout_id,
  s.warehouse_id,
  COALESCE(oa.orders_28d, 0) AS orders_28d,
  COALESCE(oa.gmv_28d, 0) AS gmv_28d,
  COALESCE(oa.unique_buyers, 0) AS unique_buyers,
  COALESCE(oa.new_buyer_share, 0) AS new_buyer_share,
  CASE WHEN COALESCE(oa.orders_28d, 0) = 0 THEN 0
       ELSE COALESCE(ra.refunds_28d, 0)::DOUBLE / oa.orders_28d
  END AS refund_rate_28d,
  COALESCE(rj.review_within_2h_share, 0) AS review_within_2h_share,
  COALESCE(dso.shared_device_order_share, 0) AS shared_device_order_share,
  COALESCE(rv.review_velocity_24h, 0) AS review_velocity_24h,
  COALESCE(rev.template_review_share, 0) AS template_review_share,
  COALESCE(rev.avg_rating, 0) AS avg_rating,
  COALESCE(rev.unverified_review_share, 0) AS unverified_review_share,
  COALESCE(sd.shared_device_peers, 0) AS shared_device_peers,
  COALESCE(sp.shared_payout_peers, 0) AS shared_payout_peers,
  COALESCE(sd.shared_device_peers, 0) + COALESCE(sp.shared_payout_peers, 0) + 1 AS component_size
FROM sellers s
LEFT JOIN order_agg oa USING (seller_id)
LEFT JOIN refund_agg ra USING (seller_id)
LEFT JOIN review_agg rev USING (seller_id)
LEFT JOIN review_join rj USING (seller_id)
LEFT JOIN review_burst rv USING (seller_id)
LEFT JOIN shared_device sd USING (seller_id)
LEFT JOIN shared_payout sp USING (seller_id)
LEFT JOIN device_share_on_orders dso USING (seller_id);
