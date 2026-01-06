# Trading Copilot (Personal)

Local-first live market forecasting + trade-zones engine.

## What you get
- Live streaming adapters (Binance public WS; Polygon + OANDA adapters included but require API keys)
- OHLCV bar builder + SQLite storage
- Multi-horizon forecasters (minutes / hours / days / weeks) with an ensemble meta-engine
- Trade plan extraction: BUY zone / SELL zone / INVALIDATION + confidence + expected duration
- FastAPI backend + Streamlit UI

## Quickstart
1. Install Python 3.11+
2. Copy `.env.example` to `.env` and fill in keys (optional for Binance only)
3. Run:
   ```bash
   cd services/core
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8080
   ```
4. In another terminal:
   ```bash
   cd services/ui
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   streamlit run streamlit_app.py
   ```

## Providers
- Binance WS works with no key.
- Polygon and OANDA need API credentials.
