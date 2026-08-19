# Metrics dictionary

| Metric | Grain | Meaning |
| --- | --- | --- |
| `orders_28d` / `gmv_28d` | buyer, seller | Volume in the scoring window |
| `refund_rate_28d` | buyer, seller | Refunds / orders |
| `keep_item_share` | buyer | Share of refunds that keep the goods |
| `discount_ratio` | buyer | Discounts / (GMV + discounts) |
| `new_buyer_share` | seller | Orders from accounts < 48h old |
| `review_within_2h_share` | seller | Reviews posted ≤ 2h after order |
| `review_velocity_24h` | seller | Peak reviews in a calendar day |
| `shared_device_peers` | seller | Other shops on mule devices (3+ shops, 2+ buyers) |
| `geo_hop_km` | order | Distance from buyer home to ship-to |
| `click_device_hhi` | creator | Herfindahl concentration of click devices |
| `self_purchase_share` | creator | Attributed orders on the creator's own device |
| `viewer_spike_z` | creator | Livestream viewer z-score vs that creator's baseline (injected) |
| precision / recall | rule pack | Hits vs synthetic `labels` table only |
