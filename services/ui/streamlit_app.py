import time
import os
import requests
import streamlit as st

# MUST be the first Streamlit command
st.set_page_config(page_title="Trading Copilot", layout="wide")

# Get API base URL - use environment variable or default to localhost
API = os.environ.get("API_BASE", "http://localhost:8080")

st.title("Trading Copilot (Personal)")

# Show streaming status
try:
    health = requests.get(f"{API}/health", timeout=2).json()
    st.success(f"✅ Core API connected (provider: {health.get('provider', 'N/A')})")
except Exception as e:
    st.error(f"❌ Cannot reach Core API at {API}")

st.markdown("---")

symbol = st.text_input("Symbol", "BTCUSDT", help="Examples: BTCUSDT, ETHUSDT, EUR_USD, GBP_USD")
interval = st.selectbox("Interval", ["1m","5m","15m","1h","4h","1d","1w"], index=3)
horizon = st.selectbox("Horizon", ["minutes","hours","days","weeks"], index=1)

col1, col2 = st.columns([1,1])

with col1:
    if st.button("Fetch forecast"):
        res = requests.post(f"{API}/v1/forecast", json={"symbol": symbol, "interval": interval, "horizon": horizon, "lookback": 300})
        st.session_state["forecast"] = res.json()

with col2:
    st.caption("💡 **Streaming is automatic!** When the Core API starts, it begins streaming live data from configured providers. Wait 2-3 minutes for bars to accumulate.")

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
