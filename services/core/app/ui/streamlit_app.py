"""
Trading Copilot - Streamlit UI

Features:
- Instrument dropdown (auto-populated from backend)
- Signal generation with confidence/trade plan
- Explanation and debug views
- Bar data visualization
"""

# -*- coding: utf-8 -*-

import os
import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime

# Page config MUST be first
st.set_page_config(
    page_title="Trading Copilot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API base URL (from environment or default)
API_BASE = os.getenv("API_BASE", "http://localhost:8080")


# ========== Helper Functions ==========

def get_health():
    """Check backend health."""
    try:
        response = requests.get(f"{API_BASE}/health", timeout=2)
        return response.json() if response.status_code == 200 else None
    except Exception:
        return None


def get_instruments(min_bars_1m=50):
    """Fetch available instruments from backend."""
    try:
        response = requests.get(
            f"{API_BASE}/v1/meta/instruments",
            params={"min_bars_1m": min_bars_1m},
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Failed to fetch instruments: {e}")
        return None


def fetch_signal(symbol, horizons, bar_limit, explain, debug):
    """Fetch signal from backend."""
    try:
        response = requests.post(
            f"{API_BASE}/v1/signal",
            json={
                "symbol": symbol,
                "horizons": horizons,
                "bar_limit": bar_limit,
                "explain": explain,
                "debug": debug,
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        st.error(f"Failed to fetch signal: {e}")
        return None


def fetch_forecast(symbol, horizon):
    """Fetch forecast from backend."""
    try:
        response = requests.post(
            f"{API_BASE}/v1/forecast",
            json={"symbol": symbol, "horizon": horizon},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        st.error(f"Failed to fetch forecast: {e}")
        return None


def fetch_bars(symbol, interval, limit):
    """Fetch bars from backend."""
    try:
        response = requests.get(
            f"{API_BASE}/v1/bars",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        st.error(f"Failed to fetch bars: {e}")
        return None


# ========== Main UI ==========

st.title("📈 Trading Copilot")
st.markdown("**AI-Powered Signal Generation & Trade Planning**")

# Check backend health
health = get_health()
if health:
    st.success(f"✅ Backend connected | Provider: {health.get('provider', 'unknown')}")
else:
    st.error("❌ Backend not reachable. Make sure the API is running.")
    st.stop()

# Fetch instruments
instruments_data = get_instruments(min_bars_1m=50)

if not instruments_data or not instruments_data.get("symbols"):
    st.warning("⚠️ No data available yet. Run backfill or wait for streaming to collect data.")
    st.info("**Quick fix**: Run `python -m app.bootstrap.run_all` to start with auto-backfill.")
    st.stop()

# ========== Sidebar Configuration ==========

st.sidebar.header("⚙️ Configuration")

# Symbol selector (dropdown)
symbols = instruments_data.get("symbols", [])
selected_symbol = st.sidebar.selectbox(
    "📊 Symbol",
    options=symbols,
    index=0 if symbols else None,
    help="Select trading instrument"
)

# Available intervals for selected symbol
available_intervals = instruments_data.get("intervals", ["1m", "5m", "15m", "1h", "4h", "1d", "1w"])

# Horizons multiselect
default_horizons = ["1m", "5m", "15m", "1h"]
horizons = st.sidebar.multiselect(
    "🔭 Horizons",
    options=[i for i in available_intervals if i != "1w"],  # Exclude 1w from horizons
    default=[h for h in default_horizons if h in available_intervals],
    help="Select multiple timeframes for analysis"
)

# Bar limit slider
bar_limit = st.sidebar.slider(
    "📏 Bar Limit (per horizon)",
    min_value=50,
    max_value=500,
    value=200,
    step=50,
    help="Max bars to fetch per horizon"
)

# Explain & Debug toggles
explain = st.sidebar.checkbox("🔍 Show Explanation", value=False)
debug = st.sidebar.checkbox("🐛 Debug Mode", value=False)

# Data readiness panel
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Data Readiness")

if selected_symbol and "counts" in instruments_data:
    symbol_counts = instruments_data["counts"].get(selected_symbol, {})
    if symbol_counts:
        for interval, count in sorted(symbol_counts.items()):
            st.sidebar.text(f"{interval}: {count} bars")
    else:
        st.sidebar.info("No count data available")

# ========== Main Content Tabs ==========

tab1, tab2, tab3 = st.tabs(["🎯 Signal", "📈 Forecast", "📊 Bars"])

# ========== TAB 1: SIGNAL ==========

with tab1:
    st.header("🎯 Signal Generation")
    
    if not horizons:
        st.warning("Please select at least one horizon in the sidebar.")
    else:
        col1, col2 = st.columns([1, 3])
        
        with col1:
            if st.button("Generate Signal", type="primary", use_container_width=True):
                with st.spinner("Generating signal..."):
                    signal_result = fetch_signal(
                        symbol=selected_symbol,
                        horizons=horizons,
                        bar_limit=bar_limit,
                        explain=explain,
                        debug=debug
                    )
                    
                    if signal_result:
                        st.session_state["signal_result"] = signal_result
        
        # Display signal if available
        if "signal_result" in st.session_state:
            result = st.session_state["signal_result"]
            
            # Main signal display
            st.markdown("### 📊 Signal Output")
            
            col_state, col_conf, col_agree = st.columns(3)
            
            with col_state:
                state = result.get("state", "UNKNOWN")
                state_colors = {
                    "STRONG_BUY": "🟢",
                    "BUY": "🟩",
                    "NEUTRAL": "⚪",
                    "SELL": "🟥",
                    "STRONG_SELL": "🔴"
                }
                st.metric("State", f"{state_colors.get(state, '⚪')} {state}")
            
            with col_conf:
                confidence = result.get("confidence", 0.0)
                st.metric("Confidence", f"{confidence:.2%}")
            
            with col_agree:
                # Agreement score is in consensus object
                consensus = result.get("consensus", {})
                agreement = consensus.get("agreement_score", 0.0)
                st.metric("Agreement", f"{agreement:.2%}")
            
            # Trade plan
            st.markdown("### 💼 Trade Plan")
            
            trade_plan = result.get("trade_plan", {})
            if trade_plan and trade_plan.get("entry_price"):
                col_entry, col_stop, col_size, col_valid = st.columns(4)
                
                with col_entry:
                    st.metric("Entry", f"${trade_plan.get('entry_price', 0):.2f}")
                
                with col_stop:
                    st.metric("Stop", f"${trade_plan.get('invalidation_price', 0):.2f}")
                
                with col_size:
                    size_pct = trade_plan.get('size_suggestion_pct', 0) * 100
                    st.metric("Size", f"{size_pct:.1f}%")
                
                with col_valid:
                    valid_ts = trade_plan.get('valid_until_ts')
                    if valid_ts:
                        valid_dt = datetime.fromtimestamp(valid_ts)
                        st.metric("Valid Until", valid_dt.strftime("%H:%M"))
            else:
                st.info("No trade plan (signal is NEUTRAL)")
            
            # Explanation (if enabled)
            if explain and "explanation" in result:
                st.markdown("### 🔍 Explanation")
                
                explanation = result["explanation"]
                
                # Drivers
                drivers = explanation.get("drivers", [])
                if drivers:
                    with st.expander("✅ Drivers (Bullish/Bearish Factors)", expanded=True):
                        for driver in drivers:
                            st.markdown(f"- {driver}")
                
                # Risks
                risks = explanation.get("risks", [])
                if risks:
                    with st.expander("⚠️ Risks (Conflicts & Warnings)", expanded=True):
                        for risk in risks:
                            st.markdown(f"- {risk}")
                
                # Notes
                notes = explanation.get("notes", [])
                if notes:
                    with st.expander("ℹ️ Notes (Neutral Observations)"):
                        for note in notes:
                            st.markdown(f"- {note}")
                
                # Confidence breakdown
                if "confidence_breakdown" in result:
                    with st.expander("🔬 Confidence Breakdown"):
                        breakdown = result["confidence_breakdown"]
                        st.json(breakdown)
            
            # Debug trace (if enabled)
            if debug and "debug_trace" in result:
                st.markdown("### 🐛 Debug Trace")
                with st.expander("Show Debug Details", expanded=False):
                    st.json(result["debug_trace"])

# ========== TAB 2: FORECAST ==========

with tab2:
    st.header("📈 Forecast")
    
    forecast_horizon = st.selectbox(
        "Forecast Horizon",
        options=["1h", "4h", "1d"],
        index=0
    )
    
    if st.button("Generate Forecast", use_container_width=True):
        with st.spinner("Generating forecast..."):
            forecast_result = fetch_forecast(
                symbol=selected_symbol,
                horizon=forecast_horizon
            )
            
            if forecast_result:
                st.session_state["forecast_result"] = forecast_result
    
    # Display forecast if available
    if "forecast_result" in st.session_state:
        result = st.session_state["forecast_result"]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Direction", result.get("direction", "unknown"))
        
        with col2:
            st.metric("Confidence", f"{result.get('confidence', 0):.2%}")
        
        with col3:
            forecast_price = result.get("forecast_price")
            if forecast_price:
                st.metric("Forecast Price", f"${forecast_price:.2f}")
        
        st.json(result)

# ========== TAB 3: BARS ==========

with tab3:
    st.header("📊 Bar Data")
    
    bar_interval = st.selectbox(
        "Interval",
        options=available_intervals,
        index=0
    )
    
    bar_fetch_limit = st.slider(
        "Number of bars",
        min_value=10,
        max_value=500,
        value=100,
        step=10
    )
    
    if st.button("Fetch Bars", use_container_width=True):
        with st.spinner("Fetching bars..."):
            bars = fetch_bars(
                symbol=selected_symbol,
                interval=bar_interval,
                limit=bar_fetch_limit
            )
            
            if bars:
                st.session_state["bars"] = bars
    
    # Display bars if available
    if "bars" in st.session_state:
        bars = st.session_state["bars"]
        
        if bars:
            # Convert to DataFrame
            df = pd.DataFrame(bars)
            
            # Convert timestamp to datetime
            df["datetime"] = pd.to_datetime(df["ts"], unit="s")
            
            # Chart
            st.subheader("📈 Price Chart")
            st.line_chart(df.set_index("datetime")["close"])
            
            # Table
            st.subheader("📋 Bar Data")
            display_df = df[["datetime", "open", "high", "low", "close", "volume"]].copy()
            display_df = display_df.sort_values("datetime", ascending=False)
            
            # Format numbers
            for col in ["open", "high", "low", "close"]:
                display_df[col] = display_df[col].apply(lambda x: f"${x:.2f}")
            display_df["volume"] = display_df["volume"].apply(lambda x: f"{x:.2f}")
            
            st.dataframe(display_df, use_container_width=True, height=400)
            
            st.info(f"Showing {len(bars)} bars for {selected_symbol} {bar_interval}")
        else:
            st.warning("No bars returned")

# ========== Footer ==========

st.sidebar.markdown("---")
st.sidebar.caption(f"🔗 API: {API_BASE}")
st.sidebar.caption("⚡ Phase 1-7 Complete")
