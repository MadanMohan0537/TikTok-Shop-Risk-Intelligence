-- Order-level scoring features for ATO and payment fraud.
CREATE OR REPLACE TABLE order_features AS
WITH buyer_hist AS (
  SELECT
    o.order_id,
    o.buyer_id,
    date_diff('day', b.created_at, o.created_at) AS account_age_days,
    date_diff('minute', i.created_at, o.created_at) AS instrument_age_minutes
  FROM orders o
  JOIN buyers b USING (buyer_id)
  LEFT JOIN instruments i USING (instrument_id)
),
prior_device AS (
  SELECT
    o.order_id,
    CASE WHEN EXISTS (
      SELECT 1 FROM orders p
      WHERE p.buyer_id = o.buyer_id
        AND p.device_id = o.device_id
        AND p.created_at < o.created_at
    ) THEN 0 ELSE 1 END AS new_device_flag
  FROM orders o
),
prior_ship AS (
  SELECT
    o.order_id,
    CASE WHEN EXISTS (
      SELECT 1 FROM orders p
      WHERE p.buyer_id = o.buyer_id
        AND p.ship_address_id = o.ship_address_id
        AND p.created_at < o.created_at
    ) THEN 0 ELSE 1 END AS new_ship_to_flag
  FROM orders o
),
geo AS (
  SELECT
    o.order_id,
    111.0 * sqrt(
      pow(o.ship_lat - b.home_lat, 2) + pow(o.ship_lon - b.home_lon, 2)
    ) AS geo_hop_km
  FROM orders o
  JOIN buyers b USING (buyer_id)
),
velocity AS (
  SELECT
    o.order_id,
    (
      SELECT COUNT(*) FROM orders p
      WHERE p.buyer_id = o.buyer_id
        AND p.created_at <= o.created_at
        AND p.created_at >= o.created_at - INTERVAL 1 HOUR
    ) AS velocity_1h
  FROM orders o
)
SELECT
  o.order_id,
  o.buyer_id,
  o.seller_id,
  o.market,
  o.created_at,
  o.gmv,
  o.discount_amount,
  o.avs_mismatch,
  o.bin_country_mismatch,
  o.auth_fail_1h,
  bh.account_age_days,
  COALESCE(bh.instrument_age_minutes, 0) AS instrument_age_minutes,
  pd.new_device_flag,
  ps.new_ship_to_flag,
  g.geo_hop_km,
  v.velocity_1h
FROM orders o
JOIN buyer_hist bh USING (order_id)
JOIN prior_device pd USING (order_id)
JOIN prior_ship ps USING (order_id)
JOIN geo g USING (order_id)
JOIN velocity v USING (order_id);
