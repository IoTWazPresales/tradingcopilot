# Setup Guide for Trading Copilot

## Quick Setup

### Step 1: Create `.env` File

Create a `.env` file in the project root with the following content:

```bash
# ========================================
# Multi-Provider Configuration
# ========================================
# Comma-separated list of providers to enable
# Options: binance, oanda
# Examples:
#   providers=binance              # Only Binance (no key needed)
#   providers=oanda                # Only OANDA (requires credentials)
#   providers=binance,oanda        # Both simultaneously
providers=binance

# ========================================
# Binance Configuration (No key needed)
# ========================================
# Comma-separated list of symbols (lowercase)
binance_symbols=btcusdt,ethusdt

# ========================================
# OANDA Configuration (Requires API key)
# ========================================
# Get credentials at: https://www.oanda.com/
# Sign up for a free practice account

# OANDA API Key (required for OANDA)
oanda_api_key=

# OANDA Account ID (required for OANDA)
oanda_account_id=

# Environment: practice or live
oanda_environment=practice

# Comma-separated list of instruments (UPPERCASE with underscores)
# FX Examples: EUR_USD,GBP_USD,USD_JPY,AUD_USD
# Index Examples: US30_USD,SPX500_USD,NAS100_USD
oanda_instruments=EUR_USD,GBP_USD,US30_USD

# ========================================
# Bar Aggregation Settings
# ========================================
bar_intervals=1m,5m,15m,1h,4h,1d,1w

# ========================================
# Database
# ========================================
sqlite_path=data/market.db

# ========================================
# Server Settings
# ========================================
host=0.0.0.0
port=8080

# ========================================
# Forecast Horizons
# ========================================
horizons=minutes,hours,days,weeks
```

### Step 2: Choose Your Setup Method

#### Option A: Docker Compose (Recommended)

```bash
# Build and run both services
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

#### Option B: Local Python

**Terminal 1 - Core API:**
```bash
cd services/core
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

**Terminal 2 - UI:**
```bash
cd services/ui
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

### Step 3: Verify Streaming is Working

Wait 2-3 minutes after startup, then run the verification script:

```bash
python verify_streaming.py
```

Or check manually via API:

```bash
# Check 1m bars for BTCUSDT
curl "http://localhost:8080/v1/bars?symbol=BTCUSDT&interval=1m&limit=10"

# Check 5m aggregated bars
curl "http://localhost:8080/v1/bars?symbol=BTCUSDT&interval=5m&limit=5"
```

## Provider-Specific Setup

### Binance (Crypto - No Key Required)

1. Set `providers=binance` in `.env`
2. Configure symbols: `binance_symbols=btcusdt,ethusdt,bnbusdt`
3. Use **lowercase** symbol names
4. No API key needed - uses public WebSocket

**Example symbols:**
- `btcusdt` - Bitcoin/USDT
- `ethusdt` - Ethereum/USDT
- `bnbusdt` - Binance Coin/USDT
- `solusdt` - Solana/USDT
- `adausdt` - Cardano/USDT

### OANDA (FX + Indices - Requires Key)

1. **Get credentials:**
   - Sign up at https://www.oanda.com/
   - Create a practice (demo) account for free
   - Generate an API key from the account dashboard
   - Note your Account ID (format: XXX-XXX-XXXXXXXX-XXX)

2. **Configure `.env`:**
   ```bash
   providers=oanda
   oanda_api_key=YOUR_API_KEY_HERE
   oanda_account_id=YOUR_ACCOUNT_ID_HERE
   oanda_environment=practice
   oanda_instruments=EUR_USD,GBP_USD,US30_USD
   ```

3. **Use UPPERCASE with underscores** for instruments

**Example instruments:**

*FX Pairs:*
- `EUR_USD` - Euro/US Dollar
- `GBP_USD` - British Pound/US Dollar
- `USD_JPY` - US Dollar/Japanese Yen
- `AUD_USD` - Australian Dollar/US Dollar
- `USD_CAD` - US Dollar/Canadian Dollar

*Indices:*
- `US30_USD` - Dow Jones 30 (CFD)
- `SPX500_USD` - S&P 500 (CFD)
- `NAS100_USD` - NASDAQ 100 (CFD)
- `UK100_GBP` - FTSE 100 (CFD)

*Commodities:*
- `XAU_USD` - Gold/US Dollar
- `XAG_USD` - Silver/US Dollar
- `WTICO_USD` - West Texas Crude Oil

**Note:** OANDA pricing stream does not include volume, so volume is set to 0.0 for all bars.

### Using Multiple Providers Simultaneously

```bash
providers=binance,oanda
binance_symbols=btcusdt,ethusdt
oanda_instruments=EUR_USD,GBP_USD,US30_USD
oanda_api_key=YOUR_KEY
oanda_account_id=YOUR_ACCOUNT
oanda_environment=practice
```

This will stream crypto from Binance and FX/indices from OANDA at the same time!

## Symbol Naming Conventions

⚠️ **Important:** Different providers use different naming conventions:

| Provider | Format | Example |
|----------|--------|---------|
| Binance  | Lowercase, no separator | `btcusdt`, `ethusdt` |
| OANDA    | Uppercase, underscore separator | `EUR_USD`, `GBP_USD` |

When querying the API, use the **normalized** format (uppercase for both):
- Binance `btcusdt` → Query as `BTCUSDT`
- OANDA `EUR_USD` → Query as `EUR_USD`

## Troubleshooting

### "No bars in database yet"

**Wait 2-3 minutes** after starting the core API. Bars accumulate over time.

### "Cannot reach Core API"

1. Check the core API is running: `curl http://localhost:8080/health`
2. Verify port 8080 is not in use by another process
3. Check logs for startup errors

### Binance not connecting

1. **Verify symbols are lowercase:** `btcusdt` not `BTCUSDT`
2. Check internet connection (WebSocket to stream.binance.com)
3. View logs: `docker-compose logs core` or check terminal output

### OANDA not connecting

1. **Verify credentials are correct** in `.env`
2. **Check instrument format:** Use `EUR_USD` not `EURUSD`
3. **Environment:** Make sure `oanda_environment=practice` (or `live` if using real account)
4. **API Key permissions:** Ensure key has "Read" permissions enabled
5. View logs for detailed error messages

### Bars are stale / not updating

1. Check logs for reconnection attempts or errors
2. Verify providers are still enabled in `.env`
3. Restart the core API: `docker-compose restart core`
4. Run verification script: `python verify_streaming.py`

## Checking Logs

**Docker Compose:**
```bash
# View logs
docker-compose logs core

# Follow logs in real-time
docker-compose logs -f core

# Last 100 lines
docker-compose logs --tail 100 core
```

**Local Python:**
Logs appear directly in the terminal where you ran `uvicorn`.

Look for messages like:
```
[Binance] BTCUSDT 1m ts=1704672060 close=42350.50000 volume=12.45
[OANDA] EUR_USD 1m ts=1704672060 close=1.09450 volume=0.00
```

## Advanced Configuration

### Changing Bar Intervals

Edit `bar_intervals` in `.env`:
```bash
# Minimal (only 1m and 1h)
bar_intervals=1m,1h

# Extended (include daily and weekly)
bar_intervals=1m,5m,15m,1h,4h,1d,1w

# Custom intervals (must be multiples of 1m)
bar_intervals=1m,3m,5m,10m,30m,1h,2h,4h,1d
```

All intervals >= 1m are automatically aggregated from 1m source bars.

### Database Location

Change `sqlite_path` in `.env`:
```bash
# Default
sqlite_path=data/market.db

# Custom location
sqlite_path=/mnt/data/trading/market.db
```

Make sure the directory exists and has write permissions.

### Inspecting the Database Directly

```bash
# Open SQLite CLI
sqlite3 data/market.db

# Show tables
.tables

# Count bars by symbol/interval
SELECT symbol, interval, COUNT(*) FROM bars GROUP BY symbol, interval;

# Show recent bars
SELECT * FROM bars ORDER BY ts DESC LIMIT 10;

# Show specific symbol
SELECT * FROM bars WHERE symbol='BTCUSDT' AND interval='1m' ORDER BY ts DESC LIMIT 20;
```

## Next Steps

Once streaming is working:

1. **Test the API endpoints:**
   - GET `/v1/bars?symbol=BTCUSDT&interval=1m&limit=100`
   - POST `/v1/forecast` with JSON body

2. **Use the Streamlit UI:**
   - Navigate to http://localhost:8501
   - Enter symbol and fetch forecast
   - View charts

3. **Build ML models:**
   - Access historical bars via the API
   - Train models using scikit-learn, XGBoost, etc.
   - Replace the baseline forecast in `main.py`

4. **Add more providers:**
   - Implement Polygon adapter for US stocks
   - Add Interactive Brokers for futures
   - Integrate Alpaca for commission-free trading

Enjoy! 🚀

