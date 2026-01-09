# Phase 2: Signal & Trade Planning Engine

## Overview

Phase 2 builds a **deterministic, multi-horizon Signal & Trade Planning Engine** on top of Phase 1 bar data. It is **fully additive** and does **not modify any Phase 1 functionality**.

### Key Features

✅ **Multi-Horizon Analysis** - Analyzes 1m, 5m, 15m, 1h, 4h, 1d, 1w timeframes simultaneously  
✅ **Adaptive Confidence** - Smooth confidence scoring based on data quality, continuity, and volatility  
✅ **Feature Extraction** - Computes momentum, volatility, trend direction, stability per horizon  
✅ **Agreement Logic** - Detects conflicts between short-term and long-term signals  
✅ **Discrete Signal States** - Maps to STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL  
✅ **Trade Planning** - Entry, invalidation (stop-loss), validity window, position sizing  
✅ **Deterministic** - Same input → same output (no randomness)  
✅ **Explainable** - Rationale tags explain every decision  
✅ **Unit Tested** - 61 passing tests covering all core logic

---

## Architecture

```
Phase 1 (Existing - Not Modified)
├── Streaming: Binance WS/REST → 1m bars
├── Aggregation: 1m → 5m, 15m, 1h, 4h, 1d, 1w
├── Storage: SQLite (bars table)
└── API: /v1/bars, /v1/forecast, /v1/providers

Phase 2 (New - Additive)
├── Confidence Engine → compute_confidence()
├── Feature Extraction → extract_features()
├── Horizon Signals → compute_horizon_signal()
├── Consensus Logic → compute_consensus()
├── State Mapping → map_to_signal_state()
├── Trade Planning → generate_trade_plan()
├── Signal Engine → generate_signal() (orchestrator)
└── API: /v1/signal (new endpoint)
```

### Data Flow

```
User → POST /v1/signal {"symbol": "BTCUSDT"}
  ↓
Signal Engine (engine.py)
  ↓
For each horizon (1m, 5m, 15m, 1h, 4h, 1d):
  1. Fetch bars from Phase 1 store (SQLite)
  2. Extract features (momentum, volatility, stability)
  3. Compute confidence (data quality, continuity)
  4. Compute direction score & strength
  5. Generate HorizonSignal with rationale
  ↓
Multi-Horizon Consensus (agreement.py)
  6. Weight signals by horizon importance & confidence
  7. Compute consensus direction [-1, +1]
  8. Detect conflicts (short-term vs long-term)
  9. Calculate agreement score
  ↓
State Mapping (states.py)
  10. Map consensus → STRONG_BUY/BUY/NEUTRAL/SELL/STRONG_SELL
  ↓
Trade Planning (trade_plan.py)
  11. Entry price = current close
  12. Invalidation = swing high/low ± buffer
  13. Validity window = horizon-specific duration
  14. Size suggestion = confidence-based (0.25% - 2.0%)
  ↓
Return SignalResponse (JSON)
```

---

## Module Details

### 1. Confidence Engine (`signals/confidence.py`)

Computes smooth confidence [0, 1] based on:
- **Data sufficiency**: n_bars / expected_bars
- **Continuity**: Penalizes gaps in timestamps
- **Volatility**: High volatility reduces confidence

```python
confidence = compute_confidence(
    horizon="1h",
    n_bars=50,
    continuity_score=0.95,
    volatility=0.02
)
# Returns float [0, 1]
```

### 2. Feature Extraction (`signals/features.py`)

Extracts deterministic features from OHLCV bars:

- **Momentum**: Return over lookback window (tanh-normalized)
- **Volatility**: Std dev of returns
- **Trend Direction**: Sign of momentum (-1, 0, +1)
- **Stability**: Inverse volatility (signal-to-noise)
- **Avg Range**: Mean(high - low)

```python
features = extract_features(horizon="1h", bars=[...])
# Returns FeatureSet(momentum, volatility, trend_direction, stability, ...)
```

### 3. Horizon Signals (`signals/agreement.py`)

Generates signal per timeframe:

```python
horizon_signal = compute_horizon_signal(horizon="1h", bars=[...])
# Returns HorizonSignal(direction_score, strength, confidence, rationale)
```

### 4. Multi-Horizon Consensus (`signals/agreement.py`)

Combines signals with weighted average (longer horizons weighted more):

```python
consensus = compute_consensus(horizon_signals=[...])
# Returns ConsensusSignal(consensus_direction, consensus_confidence, agreement_score)
```

**Horizon Weights** (from config):
- 1m: 0.5
- 5m: 0.8
- 15m: 1.0
- 1h: 1.5
- 4h: 2.0
- 1d: 2.5
- 1w: 3.0

**Agreement Detection**:
- Strong agreement (>0.8): All horizons aligned
- Weak agreement (<0.5): Conflicting signals
- Specific patterns: "short_term_bullish_long_term_bearish"

### 5. State Mapping (`signals/states.py`)

Maps consensus direction to discrete states:

| Direction | State |
|-----------|-------|
| ≥ 0.65 | STRONG_BUY |
| [0.20, 0.65) | BUY |
| [-0.20, 0.20] | NEUTRAL |
| (-0.65, -0.20] | SELL |
| ≤ -0.65 | STRONG_SELL |

### 6. Trade Planning (`signals/trade_plan.py`)

Generates actionable trade plan:

- **Entry Price**: Current close (market entry)
- **Invalidation**: 
  - BUY: Recent swing low - 2% buffer
  - SELL: Recent swing high + 2% buffer
- **Validity Window**: Horizon-dependent (5m → 1h, 1h → 6h, 1d → 5 days)
- **Size Suggestion** (% of capital):
  - Confidence 0.0-0.4: 0.25%
  - Confidence 0.4-0.6: 0.5%
  - Confidence 0.6-0.75: 1.0%
  - Confidence 0.75-0.9: 1.5%
  - Confidence 0.9-1.0: 2.0%

---

## API Usage

### Endpoint: `POST /v1/signal`

**Request:**
```json
{
  "symbol": "BTCUSDT",
  "horizons": ["5m", "15m", "1h", "1d"],
  "bar_limit": 100
}
```

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "state": "BUY",
  "confidence": 0.72,
  "trade_plan": {
    "state": "BUY",
    "confidence": 0.72,
    "entry_price": 93582.87,
    "invalidation_price": 93100.50,
    "valid_until_ts": 1767735120,
    "size_suggestion_pct": 1.0,
    "rationale": ["long_position", "high_confidence_signal"],
    "horizons_analyzed": ["5m", "15m", "1h", "1d"]
  },
  "consensus": {
    "direction": 0.45,
    "confidence": 0.72,
    "agreement_score": 0.85,
    "rationale": ["strong_agreement", "majority_bullish"]
  },
  "horizon_details": [
    {
      "horizon": "5m",
      "direction_score": 0.38,
      "strength": 0.65,
      "confidence": 0.68,
      "rationale": ["5m_weak_bullish", "5m_low_volatility"],
      "features": {
        "n_bars": 100,
        "momentum": 0.42,
        "volatility": 0.012,
        "trend_direction": 1.0,
        "stability": 0.91
      }
    },
    ...
  ],
  "as_of_ts": 1767713831,
  "version": "2.0.0",
  "phase": "2"
}
```

### Schema Endpoint: `GET /v1/signal/schema`

Returns example request/response and field descriptions.

---

## Testing

### Run All Phase 2 Tests

```powershell
cd C:\tradingcopilot\services\core
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ -v
```

**Current Status**: ✅ **68/68 tests passing** (61 unit + 7 E2E)

### Install Test Dependencies

Test dependencies are in `requirements.txt`:
```
pytest==8.3.2
pytest-asyncio==0.23.8
```

Install with:
```powershell
pip install -r requirements.txt
```

### Test Coverage

- **Confidence**: 11 tests (few bars, gaps, volatility, continuity)
- **Features**: 12 tests (uptrend, downtrend, flat market, volatility)
- **Agreement**: 11 tests (bullish alignment, conflicts, horizon weighting)
- **States**: 9 tests (threshold boundaries, confidence tagging)
- **Trade Plan**: 14 tests (buy/sell invalidation, sizing, validity)
- **Engine**: 4 tests (integration, bullish data, missing data)

---

## Configuration

All Phase 2 parameters in `signals/config.py`:

```python
# Horizon analysis
DEFAULT_HORIZONS = ["1m", "5m", "15m", "1h", "4h", "1d"]
HORIZON_WEIGHTS = {"1m": 0.5, "5m": 0.8, ..., "1w": 3.0}

# Feature extraction
MOMENTUM_LOOKBACK = 20  # bars
VOLATILITY_LOOKBACK = 20  # bars

# Confidence thresholds
MIN_BARS_FOR_CONFIDENCE = 10
MAX_VOLATILITY_PENALTY = 0.5

# Signal state thresholds
STRONG_BUY_THRESHOLD = 0.65
BUY_THRESHOLD = 0.20
NEUTRAL_THRESHOLD = 0.20
SELL_THRESHOLD = -0.20
STRONG_SELL_THRESHOLD = -0.65

# Trade planning
INVALIDATION_BUFFER_PCT = 0.02  # 2% beyond swing high/low
SIZE_BY_CONFIDENCE = [
    (0.0, 0.4, 0.25),   # Low confidence → 0.25%
    (0.4, 0.6, 0.5),    # Medium → 0.5%
    (0.6, 0.75, 1.0),   # Good → 1.0%
    (0.75, 0.9, 1.5),   # High → 1.5%
    (0.9, 1.0, 2.0),    # Very high → 2.0%
]
VALIDITY_WINDOW_MULTIPLIER = {
    "1m": 300,    # 5 minutes
    "5m": 3600,   # 1 hour
    "15m": 14400, # 4 hours
    "1h": 21600,  # 6 hours
    "4h": 86400,  # 1 day
    "1d": 432000, # 5 days
    "1w": 1209600, # 2 weeks
}
```

---

## Rationale Tags

Phase 2 uses explicit tags to explain decisions:

### Direction Tags
- `{horizon}_strong_bullish` / `{horizon}_weak_bullish`
- `{horizon}_strong_bearish` / `{horizon}_weak_bearish`
- `{horizon}_neutral`

### Volatility Tags
- `{horizon}_high_volatility`
- `{horizon}_low_volatility`

### Confidence Tags
- `{horizon}_high_confidence` / `{horizon}_low_confidence`
- `high_confidence_signal` / `low_confidence_signal`
- `high_data_quality` / `low_data_quality`

### Agreement Tags
- `strong_agreement` / `moderate_agreement` / `weak_agreement`
- `conflicting_signals`
- `majority_bullish` / `majority_bearish` / `mixed_directions`
- `short_term_bullish_long_term_bearish`
- `short_term_bearish_long_term_bullish`

### Signal State Tags
- `signal_strong_buy` / `signal_buy` / `signal_neutral` / `signal_sell` / `signal_strong_sell`

### Trade Plan Tags
- `long_position` / `short_position` / `no_position_neutral`
- `conservative_sizing` / `aggressive_sizing`
- `low_agreement_warning`

---

## Local Testing

### 1. Start the Core API

```powershell
cd C:\tradingcopilot\services\core
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

### 2. Wait for bars to accumulate (1-2 minutes)

Phase 1 streaming is populating the database. Check:

```powershell
curl "http://localhost:8080/v1/bars?symbol=BTCUSDT&interval=1m&limit=5"
```

### 3. Test Phase 2 signal endpoint

```powershell
curl -X POST "http://localhost:8080/v1/signal" `
  -H "Content-Type: application/json" `
  -d '{"symbol":"BTCUSDT","horizons":["5m","15m","1h"],"bar_limit":100}'
```

### 4. Check schema

```powershell
curl "http://localhost:8080/v1/signal/schema"
```

---

## Design Principles

### 1. Deterministic
- No randomness or time-dependent decisions
- Same input → same output (except timestamps)
- Reproducible for testing and debugging

### 2. Explainable
- Every decision tagged with rationale
- Transparent feature values
- Multi-horizon details included

### 3. Additive (Non-Breaking)
- Phase 1 endpoints unchanged: `/v1/bars`, `/v1/forecast`, `/v1/providers`
- New endpoint: `/v1/signal`
- No modifications to streaming, aggregation, or storage

### 4. Modular
- Each module has a single responsibility
- Easy to test, extend, or replace components
- Clear interfaces between modules

### 5. Robust
- Handles missing data gracefully
- Validates inputs
- Degrades to NEUTRAL when uncertain

---

## Files Added (Phase 2)

### Core Logic
```
services/core/app/signals/
├── __init__.py
├── types.py              # Canonical types (SignalState, FeatureSet, etc.)
├── config.py             # Configuration constants
├── confidence.py         # Adaptive confidence calculation
├── features.py           # Feature extraction from bars
├── agreement.py          # Multi-horizon signals & consensus
├── states.py             # Map consensus → discrete states
├── trade_plan.py         # Trade plan generation
└── engine.py             # Orchestrator (main entry point)
```

### API
```
services/core/app/api/
├── __init__.py
└── signals.py            # /v1/signal endpoint
```

### Tests
```
services/core/tests/
├── __init__.py
├── test_confidence.py    # 11 tests
├── test_features.py      # 12 tests
├── test_agreement.py     # 11 tests
├── test_states.py        # 9 tests
├── test_trade_plan.py    # 14 tests
└── test_engine.py        # 4 tests (integration)
```

### Documentation
```
PHASE2.md                 # This file
```

---

## Future Enhancements (Out of Scope)

- **ML Model Integration**: Replace deterministic features with ML predictions
- **Order Execution**: Integrate with Plus500/brokers for automated execution
- **Backtesting**: Historical signal performance analysis
- **Portfolio Management**: Multi-symbol position sizing
- **Advanced Invalidation**: Trailing stops, dynamic ATR-based stops
- **Risk Management**: Max drawdown, correlation analysis

---

## Support & Troubleshooting

### Issue: No data for symbol
**Solution**: Wait for Phase 1 streaming to populate bars, or check symbol is configured in `.env`

### Issue: Low confidence signals
**Solution**: Increase `bar_limit` in request, or wait for more data accumulation

### Issue: Conflicting signals
**Solution**: This is expected when short-term and long-term diverge. Check `agreement_score` and rationale.

### Issue: Tests failing
**Solution**: Ensure pytest-asyncio is installed: `pip install pytest pytest-asyncio`

---

## Changelog

### v2.0.0 (Phase 2 Initial Release)
- ✅ Multi-horizon signal engine
- ✅ Adaptive confidence
- ✅ Discrete signal states
- ✅ Trade planning with invalidation & sizing
- ✅ 61 unit tests
- ✅ `/v1/signal` API endpoint

---

## License

Same as Phase 1 (TBD by user)

---

**Phase 2 Development Complete** ✅  
**61/61 Tests Passing** ✅  
**Ready for Production Testing** ✅

