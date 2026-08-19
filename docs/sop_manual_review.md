# Manual review SOP — refund hold queue

**Queue:** `refund_hold`  
**Owner:** after_sales + investigations  
**SLA:** 240 minutes  
**UX guardrail:** do not block first-time legitimate returns

This SOP is for scaled associates. Investigations owns gray / network cases.

## When a case lands

A `REFUND_SERIAL_28D` hit pauses automatic refund until review. The packet includes `refund_rate_28d`, `keep_item_share`, `median_hours_to_refund`, and 28d order count.

## Steps

1. Open the case packet. Confirm market and whether the buyer is a known VIP / wholesale exception.
2. Check **order → delivery → refund timestamps**. Policy-valid returns usually sit > 48h after delivery with a single reason code.
3. Check **keep-item claims**. Two or more keep-item refunds in 28d is the primary abuse tell.
4. Check **reason-code cycling** (damaged → not as described → missing) on the same SKU family.
5. Check **device / ship-to reuse** across other new refund-heavy accounts (escalate if yes).
6. Decision:
   - **Release refund** — first-time, consistent evidence, no keep-item pattern.
   - **Uphold hold + warn** — borderline rates, ask for photo evidence.
   - **Refund ban 14d** — serial keep-item, rate ≥ 0.55, ≥ 3 refunds.
   - **Escalate to investigations** — shared device with ≥ 3 other refund actors.

## Do not

- Auto-decline a buyer with one return and a 200-day account.
- Use country of shipping alone as a fraud signal.
- Communicate “you are a fraudster” in CS macros. Use policy language.

## QA rubric (pass/fail)

| Check | Pass |
| --- | --- |
| Evidence fields cited | Packet numbers appear in the note |
| UX guardrail considered | First-time return not treated as a farm |
| Action matches ladder | No jump to `network_hold` without graph |
| SLA | Disposition timestamp within 240m |
| Appeal path | Macro includes how to submit photos |
