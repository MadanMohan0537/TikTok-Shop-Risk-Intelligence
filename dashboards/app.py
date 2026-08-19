"""Analyst console for Shop Risk Intelligence."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shop_risk.data.warehouse import connect
from shop_risk.investigation.briefing import brief_case
from shop_risk.investigation.cases import build_cases
from shop_risk.paths import DEFAULT_DB
from shop_risk.rules.engine import score_rules
from shop_risk.rules.evaluate import evaluate, threshold_curve

st.set_page_config(page_title="Shop Risk Intelligence", layout="wide")
st.title("Shop Risk Intelligence")
st.caption("Synthetic TikTok Shop-style fraud telemetry · not affiliated with TikTok / ByteDance")

db_path = st.sidebar.text_input("DuckDB path", str(DEFAULT_DB))
if not Path(db_path).exists():
    st.warning("Warehouse not found. Run `shop-risk run --demo` first.")
    st.stop()

con = connect(db_path)

try:
    kpis = con.execute("SELECT * FROM market_kpis").fetchdf()
except duckdb.Error:
    st.warning("Feature mart missing. Run `shop-risk features`.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("GMV (window)", f"{kpis['gmv'].sum():,.0f}")
c2.metric("Orders", f"{int(kpis['orders_n'].sum()):,}")
c3.metric("Refund rate", f"{(kpis['refunds_n'].sum() / max(kpis['orders_n'].sum(), 1)):.1%}")
c4.metric("Markets", f"{len(kpis)}")

hits = score_rules(con)
ev = evaluate(con, hits)
ops1, ops2, ops3 = st.columns(3)
ops1.metric("Rule hits", f"{len(hits):,}")
ops2.metric("Precision", f"{ev.overall_precision:.0%}")
ops3.metric("Recall", f"{ev.overall_recall:.0%}")

tab_mkt, tab_rules, tab_cases, tab_policy = st.tabs(
    ["Market telemetry", "Rule performance", "Investigation queue", "Policy sandbox"]
)

with tab_mkt:
    st.subheader("Market KPIs")
    st.dataframe(kpis, use_container_width=True)
    daily = con.execute("SELECT * FROM daily_market_orders").fetchdf()
    if len(daily):
        daily["dt"] = pd.to_datetime(daily["dt"])
        st.line_chart(daily.pivot_table(index="dt", columns="market", values="gmv", aggfunc="sum"))

with tab_rules:
    st.subheader("Holdout vs injected labels")
    st.dataframe(ev.to_frame(), use_container_width=True)
    if hits:
        by_rule = (
            pd.DataFrame([{"rule_id": h.rule_id, "typology": h.typology, "score": h.score} for h in hits])
            .groupby(["rule_id", "typology"])
            .size()
            .reset_index(name="hits")
        )
        st.bar_chart(by_rule.set_index("rule_id")["hits"])

with tab_cases:
    cases = build_cases(con, hits, limit=20)
    if not cases:
        st.info("No hits.")
    else:
        summary = pd.DataFrame(
            [
                {
                    "case": c.case_id,
                    "entity": c.entity_id,
                    "type": c.entity_type,
                    "typology": c.typology,
                    "market": c.market,
                    "action": c.action,
                    "score": c.score,
                }
                for c in cases
            ]
        )
        st.dataframe(summary, use_container_width=True)
        chosen = st.selectbox("Open case", [c.case_id for c in cases])
        packet = next(c for c in cases if c.case_id == chosen)
        st.markdown(brief_case(packet))

with tab_policy:
    st.subheader("What happens if we only enforce above a score cut?")
    curve = threshold_curve(con, hits)
    st.dataframe(curve, use_container_width=True)
    st.line_chart(curve.set_index("min_score")[["precision", "recall", "f1"]])
    st.caption(
        "Higher cuts buy precision (fewer CS appeals) at the cost of recall. "
        "US/UK markets in configs/markets.yaml bias toward user experience."
    )
