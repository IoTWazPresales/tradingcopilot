# Trading Copilot (Personal)

Local-first live market forecasting + trade-zones engine.

## What you get
- **Live streaming**: Binance WebSocket/REST for crypto (no API key needed!)
- **Smart fallback**: Auto-detects if WebSocket is blocked, falls back to REST polling
- **Bar aggregation**: Automatically builds 1m bars and aggregates to 5m, 15m, 1h, 4h, 1d, 1w
- **SQLite storage**: OHLCV bars stored locally with upsert support
- **Multi-horizon forecasters**: (minutes / hours / days / weeks) with baseline statistical model (ready for ML enhancement)
- **Trade plan extraction**: BUY zone / SELL zone / INVALIDATION + confidence + expected duration
- **FastAPI backend + Streamlit UI**: Clean REST API + interactive web UI

## Quickstart (Docker Compose - Recommended)

1. **Create `.env` file**:
   ```bash
   cat > .env << 'EOF'
   # Provider configuration
   providers=binance
   binance_symbols=btcusdt,ethusdt
   binance_transport=auto
   
   # Bar intervals
   bar_intervals=1m,5m,15m,1h,4h,1d,1w
   
   # Database
   sqlite_path=data/market.db
   EOF
   ```

2. **Run with Docker Compose**:
   ```bash
   docker-compose up --build
   ```

3. **Access**:
   - Core API: http://localhost:8080/docs
   - Streamlit UI: http://localhost:8501

## Quickstart (Local Python - Alternative)

1. **Install Python 3.11+**

2. **Create `.env` file** (see above)

3. **Run core API**:
   ```bash
   cd services/core
   python -m venv .venv
   
   # Activate venv:
   # Windows: .venv\Scripts\activate
   # Linux/Mac: source .venv/bin/activate
   
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8080
   ```

4. **In another terminal, run UI**:
   ```bash
   cd services/ui
   python -m venv .venv
   
   # Activate venv:
   # Windows: .venv\Scripts\activate
   # Linux/Mac: source .venv/bin/activate
   
   pip install -r requirements.txt
   streamlit run streamlit_app.py
   ```

## Verifying Live Streaming is Working

Once the core API is running, streaming starts automatically. Check that bars are being written:

### 1. Check logs
Look for log lines like:
```
BTCUSDT 1m bar stored: ts=1704672060 close=42350.50000 volume=12.45 (+6 aggregated intervals)
ETHUSDT 1m bar stored: ts=1704672060 close=2280.75000 volume=8.32 (+6 aggregated intervals)
```

### 2. Check provider status
```bash
curl "http://localhost:8080/v1/providers"
```

Output:
```json
{
  "enabled": ["binance"],
  "binance": {
    "transport": "auto",
    "active_transport": "ws",
    "symbols": ["btcusdt", "ethusdt"],
    "rest_poll_seconds": 2.0
  }
}
```

### 3. Query bars via API
Wait 2-3 minutes after startup, then:
```bash
# Check 1m bars for BTCUSDT
curl "http://localhost:8080/v1/bars?symbol=BTCUSDT&interval=1m&limit=10"

# Check 5m aggregated bars
curl "http://localhost:8080/v1/bars?symbol=BTCUSDT&interval=5m&limit=5"
```

### 4. Use the Streamlit UI
- Navigate to http://localhost:8501
- Enter a symbol (e.g., `BTCUSDT`)
- Click "Fetch forecast"
- You should see a chart with recent bars

### 5. Run verification script
```bash
python verify_streaming.py
```

## Binance Transport Modes

The system supports three transport modes for networks with different restrictions:

### `binance_transport=auto` (Default - Recommended)
- **Best for most users**
- Tries WebSocket first (fastest, real-time)
- If WebSocket handshake fails 3 times → automatically falls back to REST polling
- No manual intervention needed

### `binance_transport=ws` (WebSocket Only)
- **Use if you know WebSocket works on your network**
- Fastest, true real-time streaming
- Will fail with clear error if WebSocket is blocked

### `binance_transport=rest` (REST Polling Only)
- **Use if WebSocket is definitely blocked (corporate networks, firewalls)**
- Polls Binance REST API every 2 seconds (configurable)
- Slightly delayed but very reliable
- No WebSocket connection attempts

**To force REST mode:**
```bash
# In .env
binance_transport=rest
binance_rest_poll_seconds=2.0  # optional, default is 2.0
```

**Logs will show which mode is active:**
```
Starting Binance WebSocket (mode: ws) for symbols: ['btcusdt', 'ethusdt']
Connected to Binance WebSocket. Streaming 2 symbols.
```

Or if fallback happens:
```
Starting Binance (mode: auto) for symbols: ['btcusdt', 'ethusdt']
Binance WebSocket unavailable. Falling back to REST polling mode.
Starting Binance REST poller for 2 symbols (poll interval: 2.0s)
```

## Binance Configuration

### Symbols
- **Format**: Lowercase, no separator (e.g., `btcusdt`, `ethusdt`, `bnbusdt`)
- **No API key required**: Uses public Binance endpoints
- **Popular symbols**:
  - `btcusdt` - Bitcoin/USDT
  - `ethusdt` - Ethereum/USDT
  - `bnbusdt` - Binance Coin/USDT
  - `solusdt` - Solana/USDT
  - `adausdt` - Cardano/USDT
  - `dogeusdt` - Dogecoin/USDT

**Configure in `.env`:**
```bash
binance_symbols=btcusdt,ethusdt,bnbusdt,solusdt
```

## Plus500 / Manual Trading

This system is **data-only** for market analysis and forecasting. For Plus500 or other manual execution:

1. Use Trading Copilot to get forecasts and trade zones
2. Execute trades manually in Plus500 platform
3. No API integration needed (Plus500 doesn't offer public API)

**Workflow:**
- GET `/v1/forecast` → get BUY/SELL zones + confidence
- Manually place trades in Plus500 based on signals
- Track results in a spreadsheet or journal

## Troubleshooting

### "No bars in database yet"
**Wait 2-3 minutes** after starting. Check logs:
```bash
docker-compose logs -f core
```

### Binance WebSocket not working (Windows networks)
**Set transport mode to REST:**
```bash
# In .env
binance_transport=rest
```

Or let auto mode handle it:
```bash
# In .env
binance_transport=auto  # will automatically fallback to REST
```

### "WebSocket connection failed 3 times"
This is normal on networks that block WebSocket connections. The system will:
- **Auto mode**: Automatically switch to REST polling
- **WS mode**: Show error and stop (change to `auto` or `rest`)

### Symbols not working
- **Use lowercase**: `btcusdt` not `BTCUSDT` in configuration
- **When querying API**: Use uppercase `BTCUSDT`
- Check symbol exists on Binance: https://www.binance.com/en/trade/BTC_USDT

## Architecture Notes

- **Streaming**: Runs in background asyncio tasks, starts on FastAPI startup
- **Reconnection**: Automatic exponential backoff with jitter, never crashes the server
- **Aggregation**: 1m bars aggregated to larger timeframes on-the-fly
- **Storage**: SQLite with (symbol, interval, ts) primary key for efficient upserts
- **Graceful degradation**: No symbols → provider skipped with warning

## API Endpoints

- **GET /health** - Health check
- **GET /v1/providers** - Provider configuration and status
- **GET /v1/bars?symbol=BTCUSDT&interval=1m&limit=100** - Get historical bars
- **POST /v1/forecast** - Get forecast with trade zones

Full API docs: http://localhost:8080/docs

## Next Steps

- Replace baseline forecast with ML models (XGBoost, LSTMs, Transformers)
- Add more symbols/timeframes
- Build custom indicators (RSI, MACD, Bollinger Bands)
- Create trading journal/tracker
- Backtest strategies on historical data

---

**Note**: This is a personal trading tool for analysis and research. Not financial advice. Trade at your own risk.
