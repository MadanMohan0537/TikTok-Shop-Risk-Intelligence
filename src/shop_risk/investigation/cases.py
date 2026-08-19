from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import duckdb

from shop_risk.rules.engine import RuleHit, typology_meta


@dataclass
class CasePacket:
    case_id: str
    entity_type: str
    entity_id: str
    market: str
    typology: str
    action: str
    severity: str
    score: float
    rationale: str
    ux_guardrail: str
    evidence: dict[str, Any]
    related: dict[str, Any] = field(default_factory=dict)
    rule_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "market": self.market,
            "typology": self.typology,
            "action": self.action,
            "severity": self.severity,
            "score": self.score,
            "rationale": self.rationale,
            "ux_guardrail": self.ux_guardrail,
            "evidence": self.evidence,
            "related": self.related,
            "rule_ids": self.rule_ids,
        }


def _lookup_market(con: duckdb.DuckDBPyConnection, entity: str, entity_id: str) -> str:
    table = {
        "buyer": ("buyers", "buyer_id"),
        "seller": ("sellers", "seller_id"),
        "creator": ("creators", "creator_id"),
        "order": ("orders", "order_id"),
    }.get(entity)
    if not table:
        return "UNK"
    name, col = table
    row = con.execute(f"SELECT market FROM {name} WHERE {col} = ?", [entity_id]).fetchone()
    return str(row[0]) if row else "UNK"


def _related(con: duckdb.DuckDBPyConnection, hit: RuleHit) -> dict[str, Any]:
    if hit.entity == "buyer":
        row = con.execute(
            """
            SELECT orders_28d, gmv_28d, refund_rate_28d, discount_ratio
            FROM buyer_features WHERE buyer_id = ?
            """,
            [hit.entity_id],
        ).fetchdf()
        return row.to_dict(orient="records")[0] if len(row) else {}
    if hit.entity == "seller":
        row = con.execute(
            """
            SELECT orders_28d, gmv_28d, new_buyer_share, shared_device_peers, shared_payout_peers
            FROM seller_features WHERE seller_id = ?
            """,
            [hit.entity_id],
        ).fetchdf()
        return row.to_dict(orient="records")[0] if len(row) else {}
    if hit.entity == "creator":
        row = con.execute(
            """
            SELECT attributed_orders_28d, commission_28d, self_purchase_share, click_device_hhi
            FROM creator_features WHERE creator_id = ?
            """,
            [hit.entity_id],
        ).fetchdf()
        return row.to_dict(orient="records")[0] if len(row) else {}
    if hit.entity == "order":
        row = con.execute(
            """
            SELECT buyer_id, seller_id, gmv, geo_hop_km, new_device_flag, velocity_1h
            FROM order_features WHERE order_id = ?
            """,
            [hit.entity_id],
        ).fetchdf()
        return row.to_dict(orient="records")[0] if len(row) else {}
    return {}


def build_cases(con: duckdb.DuckDBPyConnection, hits: list[RuleHit], limit: int = 25) -> list[CasePacket]:
    """Collapse hits into a prioritized investigation queue."""
    ranked = sorted(hits, key=lambda h: (h.weight * h.score, h.score), reverse=True)
    seen: set[tuple[str, str]] = set()
    cases: list[CasePacket] = []
    for i, hit in enumerate(ranked, start=1):
        key = (hit.entity, hit.entity_id)
        if key in seen:
            # Attach extra rule ids onto the existing packet.
            for packet in cases:
                if packet.entity_id == hit.entity_id and packet.entity_type == hit.entity:
                    packet.rule_ids.append(hit.rule_id)
                    packet.score = max(packet.score, hit.score)
            continue
        seen.add(key)
        meta = typology_meta(hit.typology)
        cases.append(
            CasePacket(
                case_id=f"CASE-{i:04d}",
                entity_type=hit.entity,
                entity_id=hit.entity_id,
                market=_lookup_market(con, hit.entity, hit.entity_id),
                typology=hit.typology,
                action=hit.action,
                severity=hit.severity,
                score=round(hit.score, 4),
                rationale=hit.rationale,
                ux_guardrail=str(meta.get("ux_guardrail", "")),
                evidence=hit.evidence,
                related=_related(con, hit),
                rule_ids=[hit.rule_id],
            )
        )
        if len(cases) >= limit:
            break
    return cases
