-- Creator / affiliate / livestream integrity features.
CREATE OR REPLACE TABLE creator_features AS
WITH attributed AS (
  SELECT
    creator_id,
    COUNT(*) AS attributed_orders_28d,
    SUM(gmv) AS attributed_gmv_28d,
    SUM(gmv) * 0.08 AS commission_28d
  FROM orders
  WHERE creator_id IS NOT NULL
  GROUP BY 1
),
self_buy AS (
  SELECT
    o.creator_id,
    AVG(CASE WHEN b.buyer_id IN (
          SELECT buyer_id FROM buyers WHERE buyer_id = o.buyer_id
        ) AND starts_with(o.buyer_id, 'B_SELF_') THEN 1.0
        WHEN exists(
          SELECT 1 FROM sessions s
          WHERE s.actor_type = 'creator' AND s.actor_id = o.creator_id
            AND s.device_id = o.device_id
        ) THEN 1.0 ELSE 0.0 END) AS self_purchase_share
  FROM orders o
  JOIN buyers b ON b.buyer_id = o.buyer_id
  WHERE o.creator_id IS NOT NULL
  GROUP BY 1
),
clicks AS (
  SELECT
    creator_id,
    SUM(pow(dev_share, 2)) AS click_device_hhi
  FROM (
    SELECT
      creator_id,
      device_id,
      COUNT(*)::DOUBLE / SUM(COUNT(*)) OVER (PARTITION BY creator_id) AS dev_share
    FROM affiliate_clicks
    GROUP BY 1, 2
  )
  GROUP BY 1
),
click_conv AS (
  SELECT
    c.creator_id,
    CASE WHEN COALESCE(a.attributed_orders_28d, 0) = 0 THEN 999
         ELSE c.clicks_28d::DOUBLE / a.attributed_orders_28d
    END AS click_to_order_ratio
  FROM (
    SELECT creator_id, COUNT(*) AS clicks_28d FROM affiliate_clicks GROUP BY 1
  ) c
  LEFT JOIN attributed a USING (creator_id)
),
live AS (
  SELECT
    creator_id,
    MAX(viewer_spike_z) AS viewer_spike_z,
    MAX(CASE WHEN unique_gifters = 0 THEN 0
             ELSE gifts_gmv / NULLIF(unique_gifters, 0) END) AS gift_to_unique_payer_ratio,
    AVG(featured_brush_overlap) AS featured_brush_overlap
  FROM livestreams
  GROUP BY 1
)
SELECT
  cr.creator_id,
  cr.market,
  cr.followers,
  COALESCE(a.attributed_orders_28d, 0) AS attributed_orders_28d,
  COALESCE(a.attributed_gmv_28d, 0) AS attributed_gmv_28d,
  COALESCE(a.commission_28d, 0) AS commission_28d,
  COALESCE(sb.self_purchase_share, 0) AS self_purchase_share,
  COALESCE(ck.click_device_hhi, 0) AS click_device_hhi,
  COALESCE(cc.click_to_order_ratio, 0) AS click_to_order_ratio,
  COALESCE(lv.viewer_spike_z, 0) AS viewer_spike_z,
  COALESCE(lv.gift_to_unique_payer_ratio, 0) AS gift_to_unique_payer_ratio,
  COALESCE(lv.featured_brush_overlap, 0) AS featured_brush_overlap
FROM creators cr
LEFT JOIN attributed a USING (creator_id)
LEFT JOIN self_buy sb USING (creator_id)
LEFT JOIN clicks ck USING (creator_id)
LEFT JOIN click_conv cc USING (creator_id)
LEFT JOIN live lv USING (creator_id);
