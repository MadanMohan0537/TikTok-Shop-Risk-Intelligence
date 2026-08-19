from __future__ import annotations

from shop_risk.investigation.cases import CasePacket
from shop_risk.investigation.prompts import CASE_BRIEF_PROMPT
from shop_risk.rules.engine import action_meta


def render_prompt(case: CasePacket) -> str:
    """Fill the investigator LLM prompt from a case packet."""
    evidence_lines = "\n".join(f"- {k}: {v}" for k, v in (case.evidence or {}).items())
    related_lines = "\n".join(f"- {k}: {v}" for k, v in (case.related or {}).items())
    return CASE_BRIEF_PROMPT.format(
        entity_type=case.entity_type,
        entity_id=case.entity_id,
        market=case.market,
        typology=case.typology,
        rules_fired=", ".join(case.rule_ids),
        action=case.action,
        ux_guardrail=case.ux_guardrail,
        evidence=evidence_lines or "(none)",
        related=related_lines or "(none)",
    )


def brief_case(case: CasePacket) -> str:
    """Deterministic analyst memo (no model call). Mirrors the LLM contract."""
    sla = action_meta(case.action).get("sla_minutes", "n/a")
    owner = action_meta(case.action).get("owner", "investigations")
    evidence = "\n".join(f"| {k} | {v} |" for k, v in (case.evidence or {}).items()) or "| — | — |"
    related = "\n".join(f"- {k}: {v}" for k, v in (case.related or {}).items())
    verdict = "likely abuse" if case.score >= 0.7 else "needs more evidence"
    if case.severity == "critical":
        verdict = "abuse"

    loophole = {
        "refund_abuse": "Require delivery photo + device continuity before keep-item refunds auto-approve.",
        "brushing": "Discount new-buyer GMV in ranking until the buyer completes a second unpaid order.",
        "promo_abuse": "Bind NEWUSER coupons to a verified device graph, not account_id alone.",
        "review_manipulation": "Cap unverified reviews' weight in the 24h rating window.",
        "seller_collusion": "Block payout-instrument reuse across unrelated shop entities.",
        "ato": "Step-up on new-device + new-ship-to + geo hop instead of a hard decline.",
        "payment_fraud": "Velocity-limit new instruments with AVS mismatch before capture.",
        "affiliate_fraud": "Drop self-device attributed orders from commission eligibility.",
        "livestream_fraud": "Decouple viewer spikes from ranking unless paid-gifter diversity clears a floor.",
    }.get(case.typology, "Tighten the matching feature and add a UX holdout.")

    return f"""# {case.case_id} — {case.typology.replace('_', ' ').title()}

**Verdict:** {verdict}
**Entity:** `{case.entity_type}` `{case.entity_id}` · market `{case.market}`
**Rules:** {', '.join(case.rule_ids)}
**Action:** `{case.action}` (owner: {owner}, SLA {sla}m)
**UX guardrail:** {case.ux_guardrail}

## Story
{case.rationale} Combined risk score is **{case.score:.2f}**. The packet is prioritized
for USDS-style enforcement: stop the loss, keep the evidence trail, and avoid
collateral damage on legitimate users.

## Evidence
| Signal | Value |
| --- | --- |
{evidence}

## Related features
{related or '_none_'}

## Enforcement
Queue `{case.action}` with a reversible hold where the ladder allows it. If the
actor already has stacked hits, escalate per `configs/enforcement.yaml`.

## Loophole to close
{loophole}

## Next steps
1. Confirm the entity is not a known brand / VIP / traveler exception.
2. Pull 14d neighbor graph (shared device, payout, ship-to).
3. If the pattern is new, open an RCA and a rule-threshold review.
"""
