from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import duckdb
import pandas as pd

from shop_risk.rules.engine import RuleHit


@dataclass
class TypologyMetrics:
    typology: str
    labeled: int
    hits: int
    true_positives: int
    precision: float
    recall: float
    f1: float


@dataclass
class Evaluation:
    overall_precision: float
    overall_recall: float
    overall_f1: float
    labeled: int
    hits: int
    true_positives: int
    by_typology: list[TypologyMetrics] = field(default_factory=list)
    gmv_on_hit_orders: float = 0.0

    def to_frame(self) -> pd.DataFrame:
        rows = [
            {
                "typology": "OVERALL",
                "labeled": self.labeled,
                "hits": self.hits,
                "true_positives": self.true_positives,
                "precision": self.overall_precision,
                "recall": self.overall_recall,
                "f1": self.overall_f1,
            }
        ]
        for row in self.by_typology:
            rows.append(
                {
                    "typology": row.typology,
                    "labeled": row.labeled,
                    "hits": row.hits,
                    "true_positives": row.true_positives,
                    "precision": row.precision,
                    "recall": row.recall,
                    "f1": row.f1,
                }
            )
        return pd.DataFrame(rows)


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if den else 0.0


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def evaluate(con: duckdb.DuckDBPyConnection, hits: list[RuleHit]) -> Evaluation:
    """Score rule hits against injected ground-truth labels (synthetic only)."""
    labels = con.execute("SELECT entity_type, entity_id, typology FROM labels").fetchdf()
    label_keys = set(zip(labels["typology"], labels["entity_id"].astype(str)))
    labeled_by: dict[str, set[str]] = {}
    for _, row in labels.iterrows():
        labeled_by.setdefault(str(row["typology"]), set()).add(str(row["entity_id"]))

    hit_keys = [(h.typology, h.entity_id) for h in hits]
    tp = sum(1 for key in hit_keys if key in label_keys)

    precision = _safe_div(tp, len(hits))
    # Recall is entity-level: labeled entities recovered by any matching-typology hit.
    recovered = {key for key in hit_keys if key in label_keys}
    recall = _safe_div(len(recovered), len(label_keys))

    by_typ: list[TypologyMetrics] = []
    for typology, entities in sorted(labeled_by.items()):
        typ_hits = [h for h in hits if h.typology == typology]
        typ_hit_ids = {h.entity_id for h in typ_hits}
        typ_tp = len(typ_hit_ids & entities)
        p = _safe_div(typ_tp, len(typ_hit_ids))
        r = _safe_div(typ_tp, len(entities))
        by_typ.append(
            TypologyMetrics(
                typology=typology,
                labeled=len(entities),
                hits=len(typ_hit_ids),
                true_positives=typ_tp,
                precision=p,
                recall=r,
                f1=_f1(p, r),
            )
        )

    order_ids = [h.entity_id for h in hits if h.entity == "order"]
    gmv = 0.0
    if order_ids:
        placeholders = ",".join(["?"] * len(order_ids))
        gmv = float(
            con.execute(
                f"SELECT COALESCE(SUM(gmv), 0) FROM orders WHERE order_id IN ({placeholders})",
                order_ids,
            ).fetchone()[0]
        )

    return Evaluation(
        overall_precision=precision,
        overall_recall=recall,
        overall_f1=_f1(precision, recall),
        labeled=len(label_keys),
        hits=len(hits),
        true_positives=tp,
        by_typology=by_typ,
        gmv_on_hit_orders=gmv,
    )


def persist_evaluation(con: duckdb.DuckDBPyConnection, evaluation: Evaluation) -> None:
    df = evaluation.to_frame()
    con.register("_tmp_eval", df)
    con.execute("CREATE OR REPLACE TABLE rule_evaluation AS SELECT * FROM _tmp_eval")
    con.unregister("_tmp_eval")


def simulate_threshold(hits: list[RuleHit], labels: pd.DataFrame, min_score: float) -> dict[str, Any]:
    """Policy sandbox: precision / recall if we only enforce above a score cut."""
    kept = [h for h in hits if h.score >= min_score]
    label_keys = set(zip(labels["typology"], labels["entity_id"].astype(str)))
    tp = sum(1 for h in kept if (h.typology, h.entity_id) in label_keys)
    recovered = {(h.typology, h.entity_id) for h in kept if (h.typology, h.entity_id) in label_keys}
    p = _safe_div(tp, len(kept))
    r = _safe_div(len(recovered), len(label_keys))
    return {
        "min_score": min_score,
        "enforced": len(kept),
        "precision": p,
        "recall": r,
        "f1": _f1(p, r),
        "caught": len(recovered),
    }


def threshold_curve(con: duckdb.DuckDBPyConnection, hits: list[RuleHit]) -> pd.DataFrame:
    labels = con.execute("SELECT entity_type, entity_id, typology FROM labels").fetchdf()
    rows = [simulate_threshold(hits, labels, t) for t in (0.0, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)]
    return pd.DataFrame(rows)
