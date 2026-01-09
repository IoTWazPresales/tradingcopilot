# Phase 2 Quick Reference Card

## 🎯 What Is Phase 2?

Multi-horizon signal engine that analyzes 1m-1d timeframes and outputs:
- Discrete state: STRONG_BUY | BUY | NEUTRAL | SELL | STRONG_SELL
- Trade plan: Entry, stop-loss, size, validity window
- Explainable rationale for every decision

## 🚀 Quick Start

### Windows PowerShell

```powershell
# 1. Create and activate virtual environment
cd C:\tradingcopilot\services\core
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the core API
uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload

# 4. In a NEW PowerShell window, test the signal endpoint
cd C:\tradingcopilot
.\scripts\test_signal_live.ps1

# Or manually:
curl -X POST "http://localhost:8080/v1/signal" `
  -H "Content-Type: application/json" `
  -d '{"symbol":"BTCUSDT"}'
```

### Linux/Mac Bash

```bash
# 1. Create and activate virtual environment
cd tradingcopilot/services/core
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the core API
uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload

# 4. In a NEW terminal, test the signal endpoint
cd tradingcopilot
./scripts/test_signal_live.sh
```

## 📊 API Endpoint

### POST /v1/signal

**Request:**
```json
{
  "symbol": "BTCUSDT",              // Required
  "horizons": ["5m","1h","1d"],     // Optional (default: 1m,5m,15m,1h,4h,1d)
  "bar_limit": 100                  // Optional (default: 100)
}
```

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "state": "BUY",                   // Signal state
  "confidence": 0.72,               // [0, 1]
  "trade_plan": {
    "entry_price": 93582.87,
    "invalidation_price": 93100.50, // Stop-loss
    "valid_until_ts": 1767735120,   // Expiry timestamp
    "size_suggestion_pct": 1.0,     // % of capital
    "rationale": ["long_position", "high_confidence_signal"]
  },
  "consensus": {
    "direction": 0.45,              // [-1, +1] bearish to bullish
    "confidence": 0.72,
    "agreement_score": 0.85,        // [0, 1] alignment
    "rationale": ["strong_agreement", "majority_bullish"]
  },
  "horizon_details": [...]          // Per-timeframe analysis
}
```

## 🔧 Configuration

Edit `services/core/app/signals/config.py`:

```python
# Signal thresholds
STRONG_BUY_THRESHOLD = 0.65   # Direction ≥ 0.65
BUY_THRESHOLD = 0.20          # Direction ≥ 0.20
NEUTRAL_THRESHOLD = 0.20      # Direction in [-0.20, 0.20]
SELL_THRESHOLD = -0.20        # Direction ≤ -0.20
STRONG_SELL_THRESHOLD = -0.65 # Direction ≤ -0.65

# Position sizing (% of capital)
SIZE_BY_CONFIDENCE = [
    (0.0, 0.4, 0.25),    # Low confidence → 0.25%
    (0.4, 0.6, 0.5),     # Medium → 0.5%
    (0.6, 0.75, 1.0),    # Good → 1.0%
    (0.75, 0.9, 1.5),    # High → 1.5%
    (0.9, 1.0, 2.0),     # Very high → 2.0%
]

# Horizon weights (longer = more important)
HORIZON_WEIGHTS = {
    "1m": 0.5, "5m": 0.8, "15m": 1.0,
    "1h": 1.5, "4h": 2.0, "1d": 2.5, "1w": 3.0
}
```

## 🧪 Testing

### Run Full Test Suite

```powershell
# Windows PowerShell (from services/core with venv activated)
python -m pytest tests/ -v

# Expected: 68 passed ✅ (61 unit + 7 E2E)
```

### Run Specific Test Suites

```powershell
# Unit tests only (fast)
python -m pytest tests/test_confidence.py tests/test_features.py tests/test_agreement.py tests/test_states.py tests/test_trade_plan.py tests/test_engine.py -v

# E2E tests only (slower, creates temp database)
python -m pytest tests/test_signal_e2e_sqlite.py -v

# Specific module
python -m pytest tests/test_confidence.py -v
```

### Install Test Dependencies

If pytest is missing:

```powershell
pip install pytest pytest-asyncio
```

This is already included in `requirements.txt`.

## 📦 Module Overview

```
signals/
├── engine.py         # Main orchestrator (start here)
├── confidence.py     # Data quality scoring
├── features.py       # Momentum, volatility, trend
├── agreement.py      # Multi-horizon consensus
├── states.py         # Map to discrete signals
├── trade_plan.py     # Entry/stop/size/validity
├── types.py          # Data structures
└── config.py         # Configuration constants
```

## 🔍 Understanding Output

### Signal States
- **STRONG_BUY**: Direction ≥ 0.65 (strong bullish)
- **BUY**: Direction ≥ 0.20 (weak bullish)
- **NEUTRAL**: Direction in [-0.20, 0.20]
- **SELL**: Direction ≤ -0.20 (weak bearish)
- **STRONG_SELL**: Direction ≤ -0.65 (strong bearish)

### Confidence Scores
- **0.9-1.0**: Very high (2.0% position)
- **0.75-0.9**: High (1.5% position)
- **0.6-0.75**: Good (1.0% position)
- **0.4-0.6**: Medium (0.5% position)
- **0.0-0.4**: Low (0.25% position)

### Agreement Score
- **>0.8**: Strong agreement (all horizons aligned)
- **0.6-0.8**: Moderate agreement
- **<0.5**: Weak agreement (conflicting signals)

### Common Rationale Tags
- `strong_agreement` - All horizons aligned
- `conflicting_signals` - Short vs long term diverge
- `short_term_bullish_long_term_bearish` - Specific conflict
- `high_confidence_signal` - Good data quality
- `low_agreement_warning` - Conflicting horizons detected
- `conservative_sizing` - Small position suggested
- `long_position` / `short_position` - Trade direction

## 🛠️ Troubleshooting

### "No data for symbol"
→ Wait for Phase 1 streaming to populate bars (check `/v1/bars`)

### Low confidence signals
→ Increase `bar_limit` or wait for more data accumulation

### Conflicting signals
→ Expected when short/long term diverge. Check `agreement_score`

### Tests failing
→ Ensure `pytest pytest-asyncio` installed in venv

## 📚 Documentation

- **Comprehensive**: [PHASE2.md](PHASE2.md)
- **Deliverables**: [PHASE2_DELIVERABLES.md](PHASE2_DELIVERABLES.md)
- **This card**: Quick reference

## ✅ Status

- **Tests**: 61/61 passing ✅
- **Phase 1**: Unchanged ✅
- **Breaking changes**: None ✅
- **Ready for**: Production testing

## 🎓 Key Concepts

1. **Multi-horizon**: Analyzes multiple timeframes simultaneously
2. **Consensus**: Weighted average of horizon signals
3. **Agreement**: How well horizons align (conflict detection)
4. **Adaptive confidence**: Data quality affects signal strength
5. **Deterministic**: Same input → same output (no randomness)
6. **Explainable**: Rationale tags explain decisions

## 💡 Example Workflow

```
1. User requests signal for BTCUSDT
2. Engine fetches bars for 1m, 5m, 15m, 1h, 4h, 1d
3. For each horizon:
   - Extract features (momentum, volatility)
   - Compute confidence (data quality)
   - Generate direction score
4. Compute weighted consensus
5. Detect conflicts (short vs long term)
6. Map to discrete state (BUY/SELL/NEUTRAL)
7. Generate trade plan:
   - Entry = current price
   - Stop-loss = swing high/low ± 2%
   - Size = confidence-based (0.25%-2.0%)
   - Validity = horizon-specific window
8. Return JSON with rationale
```

## 🔗 Related Endpoints

- `GET /health` - API health
- `GET /v1/bars` - Raw OHLCV data
- `POST /v1/forecast` - Time-series forecast (Phase 1)
- `GET /v1/providers` - Data provider status
- **POST /v1/signal** - Multi-horizon signal (Phase 2) ⭐

---

**Phase 2 Version**: 2.0.0  
**Last Updated**: January 2026  
**Status**: Production-ready ✅

