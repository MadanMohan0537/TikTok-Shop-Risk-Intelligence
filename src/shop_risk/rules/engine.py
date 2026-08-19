from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import duckdb
import pandas as pd

from shop_risk.config import enforcement, rules_pack, typologies


@dataclass
class RuleHit:
    rule_id: str
    typology: str
    entity: str
    entity_id: str
    severity: str
    action: str
    weight: float
    score: float
    rationale: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "items"):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (float, int, str, bool)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def score_rules(con: duckdb.DuckDBPyConnection) -> list[RuleHit]:
    """Run each YAML rule's SQL against the feature mart and collect hits."""
    hits: list[RuleHit] = []
    for rule in rules_pack()["rules"]:
        result = con.execute(rule["sql"]).fetchdf()
        for row in result.to_dict(orient="records"):
            hits.append(
                RuleHit(
                    rule_id=rule["id"],
                    typology=rule["typology"],
                    entity=rule["entity"],
                    entity_id=str(row["entity_id"]),
                    severity=rule["severity"],
                    action=rule["action"],
                    weight=float(rule["weight"]),
                    score=float(row["score"]),
                    rationale=rule["rationale"],
                    evidence=_jsonable(row.get("evidence")) or {},
                )
            )
    return escalate(hits)


def escalate(hits: list[RuleHit]) -> list[RuleHit]:
    """Apply the repeat-strike ladder from enforcement.yaml."""
    ladder = enforcement().get("repeat_escalation", [])
    by_entity: dict[str, list[RuleHit]] = {}
    for hit in hits:
        by_entity.setdefault(hit.entity_id, []).append(hit)

    strike_map = {int(step["strikes"]): step.get("escalate_to") for step in ladder}
    for entity_hits in by_entity.values():
        n = len(entity_hits)
        target = None
        for strikes in sorted(strike_map):
            if n >= strikes and strike_map[strikes]:
                target = strike_map[strikes]
        if target:
            for hit in entity_hits:
                if hit.action != target:
                    hit.action = target
                    hit.severity = "critical"
    return hits


def hits_frame(hits: list[RuleHit]) -> pd.DataFrame:
    if not hits:
        return pd.DataFrame(
            columns=[
                "rule_id",
                "typology",
                "entity",
                "entity_id",
                "severity",
                "action",
                "weight",
                "score",
                "rationale",
            ]
        )
    rows = []
    for hit in hits:
        row = hit.to_dict()
        row.pop("evidence", None)
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["score", "weight"], ascending=False).reset_index(drop=True)


def persist_hits(con: duckdb.DuckDBPyConnection, hits: list[RuleHit]) -> None:
    df = hits_frame(hits)
    con.register("_tmp_hits", df)
    con.execute("CREATE OR REPLACE TABLE rule_hits AS SELECT * FROM _tmp_hits")
    con.unregister("_tmp_hits")


def action_meta(action: str) -> dict[str, Any]:
    return dict(enforcement()["actions"].get(action, {}))


def typology_meta(typology: str) -> dict[str, Any]:
    return dict(typologies().get(typology, {}))
