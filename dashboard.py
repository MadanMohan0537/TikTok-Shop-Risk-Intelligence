import os

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="ShopGuard Risk Intelligence", page_icon="🛡️", layout="wide")
API = st.sidebar.text_input("API URL", os.getenv("API_URL", "http://localhost:8000")).rstrip("/")
st.title("🛡️ ShopGuard Risk Intelligence")
st.caption("Independent portfolio project · Synthetic marketplace data · Not affiliated with TikTok")


def get(path: str):
    response = requests.get(f"{API}{path}", timeout=10)
    response.raise_for_status()
    return response.json()


try:
    overview = get("/analytics/overview")
except requests.RequestException:
    st.error("Start the API with: uvicorn app.main:app --reload")
    st.stop()

tabs = st.tabs(["Risk Overview", "Investigation Queue", "Fraud Rings", "Policy Simulator"])
with tabs[0]:
    cols = st.columns(5)
    cols[0].metric("Orders", overview["orders"])
    cols[1].metric("GMV", f"${overview['gmv']:,.0f}")
    cols[2].metric("Fraud rate", f"{overview['fraud_rate']}%")
    cols[3].metric("Blocked", overview["blocked"])
    cols[4].metric("Open cases", overview["open_cases"])
    trends = pd.DataFrame(get("/analytics/trends"))
    st.subheader("Marketplace telemetry")
    st.line_chart(trends.set_index("day")[["orders", "fraud_orders"]])
    st.subheader("Most-triggered controls")
    st.dataframe(pd.DataFrame(get("/analytics/rules")), use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("Prioritized analyst queue")
    st.dataframe(pd.DataFrame(get("/cases")), use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("Shared-device network candidates")
    st.write("Clusters are prioritized when multiple buyers and sellers share a device identifier.")
    st.dataframe(pd.DataFrame(get("/rings")), use_container_width=True, hide_index=True)

with tabs[3]:
    threshold = st.slider("Enforcement threshold", 0, 100, 60, 5)
    result = get(f"/policy/simulate?min_score={threshold}")
    cols = st.columns(5)
    cols[0].metric("Affected orders", result["affected_orders"])
    cols[1].metric("Fraud captured", result["fraud_captured"])
    cols[2].metric("False positives", result["false_positives"])
    cols[3].metric("Fraud value captured", f"${result['fraud_value_captured']:,.2f}")
    cols[4].metric("Precision / Recall", f"{result['precision']}% / {result['recall']}%")
    st.info("Use this view to compare fraud prevention with legitimate-user friction before changing a policy.")
