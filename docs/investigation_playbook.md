# Investigation playbook

Use this when a rule is noisy, a partner team escalates, or a market KPI moves.

## 1. Frame the question

- What actor (buyer / seller / creator / network)?
- What money or trust object (GMV, ranking, coupon, commission, payout)?
- What user-experience cost if we over-enforce?

## 2. Pull the mart, not the raw dump

Start from `buyer_features`, `seller_features`, `creator_features`, or `order_features`. If the feature you need is missing, add it in `sql/` and version the rule — do not special-case in a notebook.

## 3. Compare against typology priors

`configs/fraud_typology.yaml` lists the signals that should move if the story is real. If refund rate is high but keep-item share is ~0, you likely have a logistics quality issue, not friendly fraud.

## 4. Graph the neighbors

Shared device (mule-filtered), shared payout, shared ship-to. Isolated accounts get a reversible action. Components ≥ 5 go to `network_hold`.

## 5. Write the packet

`shop-risk investigate --prompt` fills the LLM case-brief contract. Keep confirmed signals and hypotheses in separate bullets. Recommend **one** action from `configs/enforcement.yaml`.

## 6. Close the loophole

Every case should end with a product or policy ask (see the “Loophole to close” section of the memo). File it with the partner team that owns the surface: after_sales, payments_risk, discovery, creator_ops, seller_integrity.

## 7. Measure

Ship the rule behind a score cut. Watch 14-day precision, CS appeal rate, and GMV on hit orders. If US/UK appeal rate jumps, raise the threshold — those markets are configured with `enforcement_bias: user_experience`.
