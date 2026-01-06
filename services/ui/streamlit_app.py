import time
import requests
import streamlit as st

API = st.secrets.get("API_BASE", "http://core:8080")

st.set_page_config(page_title="Trading Copilot", layout="wide")
st.title("Trading Copilot (Personal)")

symbol = st.text_input("Symbol", "btcusdt")
interval = st.selectbox("Interval", ["1m","5m","15m","1h","4h","1d","1w"], index=3)
horizon = st.selectbox("Horizon", ["minutes","hours","days","weeks"], index=1)

col1, col2 = st.columns([1,1])

with col1:
    if st.button("Fetch forecast"):
        res = requests.post(f"{API}/v1/forecast", json={"symbol": symbol, "interval": interval, "horizon": horizon, "lookback": 300})
        st.session_state["forecast"] = res.json()

with col2:
    st.caption("Tip: Run a provider stream later (Cursor) to populate bars. This UI is wired to the core API.")

fc = st.session_state.get("forecast")
if fc:
    st.subheader("Forecast")
    st.json(fc)

    st.subheader("Recent bars")
    bars = requests.get(f"{API}/v1/bars", params={"symbol": symbol, "interval": interval, "limit": 200}).json()
    if bars:
        import pandas as pd
        df = pd.DataFrame(bars)
        df["dt"] = pd.to_datetime(df["ts"], unit="s")
        st.line_chart(df.set_index("dt")["close"])
    else:
        st.info("No stored bars yet. Once you add a provider stream, bars will show here.")
