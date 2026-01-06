# Binance-Only Implementation with Transport Fallback

## Summary

Implemented a robust Binance-only data pipeline with automatic WebSocket→REST fallback for Windows networks where WebSocket handshakes may fail.

## What Changed

### 1. Default Provider Set to Binance Only
- **Before**: Empty providers string, required manual configuration
- **After**: `providers=binance` by default
- OANDA disabled by default (can still be enabled manually)

### 2. Binance Transport Modes
Added three transport modes to handle network restrictions:

#### Auto Mode (Default)
```bash
binance_transport=auto  # Tries WS, falls back to REST
```
- Tries WebSocket first (fastest)
- If 3 consecutive handshake failures → switches to REST
- **Recommended for all users**

#### REST Mode (Explicit)
```bash
binance_transport=rest
binance_rest_poll_seconds=2.0
```
- Forces REST polling only
- **Use when WebSocket is known to be blocked**
- Polls Binance API every N seconds

#### WebSocket Mode (Explicit)
```bash
binance_transport=ws
```
- Forces WebSocket only
- Fails with clear error if unavailable

### 3. WebSocket Improvements
- Added explicit timeouts: `open_timeout=10`, `ping_interval=20`, `ping_timeout=20`
- Tracks consecutive handshake failures
- Raises `BinanceWsUnavailable` exception after 3 failures in fail-fast mode
- Better error messages for Windows network issues

### 4. REST Provider Implementation
**New file**: `services/core/app/providers/binance_rest.py`
- Polls `GET /api/v3/klines?symbol=BTCUSDT&interval=1m&limit=2`
- Uses **second-to-last kline** (index -2) because last kline is often still open
- Deduplicates bars based on timestamp
- Maps lowercase config symbols to uppercase API symbols
- Configurable poll interval (default 2.0 seconds)

### 5. Smart Fallback Logic in Runner
**Modified**: `services/core/app/streaming/runner.py`
- `_start_binance()` now checks `binance_transport` setting
- `_start_binance_ws()` with fail_fast parameter
- `_start_binance_rest()` for REST mode
- Auto mode tries WS first, catches `BinanceWsUnavailable`, starts REST
- Tracks `active_binance_transport` (ws/rest)

### 6. Improved Logging
**Modified**: `services/core/app/streaming/aggregator.py`
- **Throttled logging**: Once per minute per symbol (not every bar)
- Log format: `BTCUSDT 1m bar stored: ts=... close=... volume=... (+6 aggregated intervals)`
- Reduces log spam from 60 lines/hour to 1 line/hour per symbol

### 7. New API Endpoint
**Added**: `GET /v1/providers`

Returns:
```json
{
  "enabled": ["binance"],
  "binance": {
    "transport": "auto",
    "active_transport": "ws",
    "symbols": ["btcusdt", "ethusdt"],
    "rest_poll_seconds": 2.0
  },
  "oanda": {
    "configured": false,
    "instruments": [],
    "environment": "practice"
  }
}
```

### 8. Documentation Updates
- **README.md**: Complete rewrite focusing on Binance-only setup
- **QUICKSTART.md**: Simplified 3-minute getting started guide
- Removed OANDA examples from main docs (still works if manually enabled)
- Added transport mode explanations
- Added Windows/corporate network troubleshooting

---

## Files Changed/Added

### Added (1 file)
1. `services/core/app/providers/binance_rest.py` - REST polling implementation

### Modified (6 files)
1. `services/core/app/config.py` - Added transport settings, changed default
2. `services/core/app/providers/binance_ws.py` - Timeouts, fail-fast mode, exception
3. `services/core/app/streaming/runner.py` - Transport mode selection, fallback logic
4. `services/core/app/streaming/aggregator.py` - Throttled logging
5. `services/core/app/main.py` - Added `/v1/providers` endpoint
6. `README.md` - Complete rewrite for Binance-only focus

### Documentation (2 files)
1. `QUICKSTART.md` - Updated for Binance-only
2. `BINANCE_ONLY_CHANGES.md` - This file

**Total: 9 files**

---

## How to Run

### Quick Start (Local Python)

```bash
# 1. Create .env file
cat > .env << 'EOF'
providers=binance
binance_symbols=btcusdt,ethusdt
binance_transport=auto
bar_intervals=1m,5m,15m,1h,4h,1d,1w
sqlite_path=data/market.db
EOF

# 2. Install and run (Windows example)
cd services/core
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

### Docker Compose

```bash
# 1. Create .env (same as above)

# 2. Run
docker-compose up --build
```

---

## Expected Behavior

### Startup Logs (Auto Mode - WebSocket Success)
```
Starting streaming runner...
Enabled providers: ['binance']
Starting Binance (mode: auto) for symbols: ['btcusdt', 'ethusdt']
Connecting to Binance WebSocket: ['btcusdt', 'ethusdt']
Connected to Binance WebSocket. Streaming 2 symbols.
Started 1 provider task(s).
```

### Startup Logs (Auto Mode - WebSocket Failed, REST Fallback)
```
Starting streaming runner...
Enabled providers: ['binance']
Starting Binance (mode: auto) for symbols: ['btcusdt', 'ethusdt']
Connecting to Binance WebSocket: ['btcusdt', 'ethusdt']
Binance WebSocket connection error (attempt 1): [Errno 10060] Connect call failed
Binance WebSocket connection error (attempt 2): [Errno 10060] Connect call failed
Binance WebSocket connection error (attempt 3): [Errno 10060] Connect call failed
Binance WebSocket unavailable after 3 consecutive connection failures.
Binance WebSocket unavailable. Falling back to REST polling mode.
Starting Binance REST poller for 2 symbols (poll interval: 2.0s)
Started 1 provider task(s).
```

### Bar Storage Logs (Once per minute per symbol)
```
BTCUSDT 1m bar stored: ts=1704672060 close=42350.50000 volume=12.45 (+6 aggregated intervals)
ETHUSDT 1m bar stored: ts=1704672060 close=2280.75000 volume=8.32 (+6 aggregated intervals)
```

---

## Force REST Mode (For Known Blocked Networks)

If you know WebSocket won't work:

```bash
# In .env
binance_transport=rest
binance_rest_poll_seconds=2.0
```

This skips WebSocket attempts entirely and goes straight to REST polling.

---

## Verify It's Working

### 1. Check provider status
```bash
curl "http://localhost:8080/v1/providers"
```

Look for `"active_transport": "ws"` or `"active_transport": "rest"`

### 2. Check bars
```bash
curl "http://localhost:8080/v1/bars?symbol=BTCUSDT&interval=1m&limit=10"
```

Should return recent bars (wait 2-3 minutes after startup)

### 3. Run verification script
```bash
python verify_streaming.py
```

---

## Key Design Decisions

### Why Index -2 for REST Klines?
Binance REST `/klines` endpoint returns:
- Index -1: Current/open kline (not finalized)
- Index -2: Last closed kline (finalized)

We only emit finalized bars to match WebSocket behavior.

### Why 2 Second Poll Interval?
- Binance rate limit: 1200 requests/minute = 20/second
- With 10 symbols: 10 requests every 2 seconds = 5 req/sec
- Safe margin: Can support 40+ symbols before hitting limits

### Why Auto Mode by Default?
- WebSocket is preferred (faster, more efficient)
- REST fallback ensures reliability on all networks
- Users don't need to know about network restrictions upfront

### Why Throttle Logging?
- 60 bars/hour per symbol = too much log spam
- 1 log/minute per symbol = enough to verify streaming works
- Aggregator handles logging (not runner) for centralized control

---

## Assumptions & Limitations

### Symbol Naming
- **Config**: Lowercase (e.g., `btcusdt`)
- **API Queries**: Uppercase (e.g., `BTCUSDT`)
- **Storage**: Uppercase (normalized)

### REST Mode Delay
- ~2 second delay vs WebSocket real-time
- Acceptable for most use cases (forecasting, not HFT)
- Can reduce `binance_rest_poll_seconds` to 1.0 if needed (watch rate limits)

### No OANDA by Default
- Can still be enabled by setting `providers=binance,oanda`
- Requires manual configuration (not documented in main README)
- Focus is Binance-only for simplicity

---

## Testing Checklist

- [x] Auto mode works with WebSocket available
- [x] Auto mode falls back to REST when WebSocket blocked
- [x] REST mode works explicitly
- [x] WS mode works explicitly
- [x] Logs are throttled to once per minute per symbol
- [x] `/v1/providers` endpoint returns correct status
- [x] Bars are stored correctly in both modes
- [x] Aggregation works in both modes
- [x] No linter errors
- [x] Docker Compose builds and runs
- [x] Local venv setup works

---

## Future Enhancements

1. **Retry logic for REST**: Currently polls continuously, could add backoff on repeated errors
2. **Rate limit monitoring**: Track remaining requests, throttle if approaching limit
3. **Metrics endpoint**: `/v1/metrics` with bar counts, uptime, errors
4. **Multiple REST workers**: For very large symbol lists, parallelize REST requests
5. **WebSocket reconnection tuning**: Adjust timeout/retry parameters based on network

---

## Contact & Support

For issues:
1. Check logs: `docker-compose logs -f core` or terminal output
2. Run `python verify_streaming.py`
3. Try forcing REST mode: `binance_transport=rest`
4. Check firewall/antivirus settings

Enjoy reliable Binance streaming! 🚀📈

