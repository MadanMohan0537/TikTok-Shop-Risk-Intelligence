from __future__ import annotations

import duckdb
import pandas as pd

from shop_risk.rules.engine import RuleHit


def market_snapshot(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("SELECT * FROM market_kpis").fetchdf()


def daily_orders(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("SELECT * FROM daily_market_orders").fetchdf()


def rule_ops_kpis(hits: list[RuleHit], evaluation_frame: pd.DataFrame) -> dict[str, float | int]:
    """Ops dashboard numbers an analyst would quote in standup."""
    return {
        "queues_open": len({(h.entity, h.entity_id) for h in hits}),
        "hits": len(hits),
        "critical_hits": sum(1 for h in hits if h.severity == "critical"),
        "precision": float(evaluation_frame.loc[evaluation_frame["typology"] == "OVERALL", "precision"].iloc[0])
        if len(evaluation_frame)
        else 0.0,
        "recall": float(evaluation_frame.loc[evaluation_frame["typology"] == "OVERALL", "recall"].iloc[0])
        if len(evaluation_frame)
        else 0.0,
    }


def hits_by_typology(hits: list[RuleHit]) -> pd.DataFrame:
    if not hits:
        return pd.DataFrame(columns=["typology", "hits", "entities"])
    df = pd.DataFrame([{"typology": h.typology, "entity_id": h.entity_id} for h in hits])
    return (
        df.groupby("typology")
        .agg(hits=("entity_id", "size"), entities=("entity_id", "nunique"))
        .reset_index()
        .sort_values("hits", ascending=False)
    )
