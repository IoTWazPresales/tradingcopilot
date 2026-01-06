# Quick Start Guide - Trading Copilot

## 🚀 Get Running in 3 Minutes

### Step 1: Configure Environment (30 seconds)

Create `.env` file in project root:

```bash
cat > .env << 'EOF'
# Binance configuration (no API key needed!)
providers=binance
binance_symbols=btcusdt,ethusdt
binance_transport=auto

# Bar intervals  
bar_intervals=1m,5m,15m,1h,4h,1d,1w

# Database
sqlite_path=data/market.db
EOF
```

### Step 2: Start Services (1 min)

```bash
docker-compose up --build
```

### Step 3: Wait & Verify (2 min)

Wait 2-3 minutes for bars to accumulate, then:

```bash
# Check provider status
curl "http://localhost:8080/v1/providers"

# Check bars
curl "http://localhost:8080/v1/bars?symbol=BTCUSDT&interval=1m&limit=10" | python -m json.tool
```

Or run verification script:
```bash
python verify_streaming.py
```

### Step 4: Open UI

Navigate to http://localhost:8501

- Enter symbol: `BTCUSDT`
- Select interval: `1h`
- Click "Fetch forecast"
- View chart and prediction

**Done!** 🎉

---

## Transport Modes (For Network Issues)

### Auto Mode (Default - Recommended)
```bash
binance_transport=auto
```
- Tries WebSocket first (fastest)
- Falls back to REST if WebSocket fails
- **Best for most users**

### Force REST Mode (For Restrictive Networks)
```bash
binance_transport=rest
binance_rest_poll_seconds=2.0
```
- **Use if WebSocket is blocked** (corporate networks, firewalls, some ISPs)
- Polls REST API every 2 seconds
- Very reliable, slight delay (~2s)

### WebSocket Only Mode
```bash
binance_transport=ws
```
- Fastest, real-time
- Fails loudly if WebSocket blocked

---

## Troubleshooting

### "No bars in database yet"
**Wait 2-3 minutes** after starting. Check logs:
```bash
docker-compose logs -f core
```

### WebSocket not working (Windows/Corporate networks)
**Use REST mode:**
```bash
# In .env
binance_transport=rest
```

Or just use `auto` - it will fallback automatically!

---

## What's Happening?

1. **Core API starts** → Streaming runner initializes
2. **Binance connects** → WebSocket or REST mode
3. **1m bars stream in** → Real-time or every 2 seconds
4. **Aggregator runs** → Computes 5m, 15m, 1h, 4h, 1d, 1w
5. **SQLite stores bars** → Upserts with conflict handling
6. **API serves data** → `/v1/bars` and `/v1/forecast` endpoints
7. **UI displays** → Charts and predictions

All happens **automatically** on startup! 🔄

---

## Adding More Symbols

Edit `.env`:
```bash
binance_symbols=btcusdt,ethusdt,bnbusdt,solusdt,adausdt
```

Restart:
```bash
docker-compose restart core
```

Popular symbols: `btcusdt`, `ethusdt`, `bnbusdt`, `solusdt`, `adausdt`, `dogeusdt`, `xrpusdt`

---

## Local Python (Without Docker)

```bash
# Terminal 1 - Core API
cd services/core
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# Terminal 2 - UI
cd services/ui  
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
streamlit run streamlit_app.py
```

---

## Next Steps

- Check `README.md` for detailed documentation
- Check `SETUP.md` for advanced configuration
- Explore API docs: http://localhost:8080/docs

Enjoy! 📊💹
