# Worked RCA — serial keep-item refunds (US)

**Window:** 28 days ending 2026-08-18 (synthetic)  
**Trigger:** refund GMV ratio in US above the other high-trust markets  
**Owner analog:** USDS Risk Control, after_sales partner

## What changed

Injected `refund_abuse` buyers place 5–8 delivered orders and refund most of them within 36 hours, majority keep-item. Honest refunds in the generator are ~6% of orders, slower, and keep-item false.

## Mechanism

Friendly-fraud pattern: confirm delivery → file a keep-item claim before CS can request photos → cycle reason codes. The gap is **auto-approve of keep-item on new-ish repeat refunders**.

## Why a naive refund-rate rule is not enough

A 40% refund rate on a shop with a bad batch of SKUs is a quality problem. The discriminating features are:

- `refunds_28d >= 3` and `orders_28d >= 4`
- `refund_rate_28d >= 0.55`
- `keep_item_share >= 0.4`
- `median_hours_to_refund <= 36`

That combination is `REFUND_SERIAL_28D`.

## Enforcement that protects UX

Default action is `refund_hold` (reversible, 240m SLA), **not** a payment block. First-time legitimate returns stay out of the WHERE clause (`orders_28d >= 4`).

## Product ask

Require a delivery photo (or device continuity with the original session) before keep-item auto-approves on accounts with ≥ 2 refunds in 28d.

## 14-day watch

- Precision of `REFUND_SERIAL_28D` (target ≥ 0.8 on the labeled holdout)
- CS appeal rate on held refunds
- Repeat-refund GMV in US vs UK
