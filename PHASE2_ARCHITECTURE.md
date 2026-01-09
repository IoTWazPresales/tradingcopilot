# Phase 2 Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TRADING COPILOT                                  │
│                         Phase 1 + Phase 2                                │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                            PHASE 1 (Unchanged)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌───────────────┐      ┌──────────────┐      ┌──────────────┐         │
│  │ Binance WS/   │ ───> │ Bar          │ ───> │ SQLite       │         │
│  │ REST Poller   │      │ Aggregator   │      │ Store        │         │
│  └───────────────┘      └──────────────┘      └──────────────┘         │
│         │                      │                      │                 │
│         │ 1m ticks/klines      │ 5m,15m,1h,4h,1d,1w  │ Upsert          │
│         v                      v                      v                 │
│                                                                          │
│  API Endpoints:                                                          │
│  • GET /v1/bars          • POST /v1/forecast                            │
│  • GET /v1/providers     • GET /health                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Bars stored in SQLite
                                    v
┌─────────────────────────────────────────────────────────────────────────┐
│                            PHASE 2 (New)                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  User Request: POST /v1/signal {"symbol": "BTCUSDT"}                    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      SIGNAL ENGINE                               │  │
│  │                      (engine.py)                                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                             │                                            │
│                             v                                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Step 1: Fetch bars for all horizons (1m, 5m, 15m, 1h, 4h, 1d)  │  │
│  │          from Phase 1 SQLite store                               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                             │                                            │
│                             v                                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  For EACH horizon:                                               │  │
│  │                                                                  │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │  FEATURE EXTRACTION (features.py)                       │   │  │
│  │  │  • Momentum: tanh(return over lookback)                 │   │  │
│  │  │  • Volatility: std dev of returns                       │   │  │
│  │  │  • Trend Direction: sign of momentum (-1, 0, +1)        │   │  │
│  │  │  • Stability: inverse volatility                        │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  │                             │                                    │  │
│  │                             v                                    │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │  CONFIDENCE SCORING (confidence.py)                     │   │  │
│  │  │  • Data sufficiency: n_bars / expected                  │   │  │
│  │  │  • Continuity: gap detection in timestamps              │   │  │
│  │  │  • Volatility penalty: high vol reduces confidence      │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  │                             │                                    │  │
│  │                             v                                    │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │  HORIZON SIGNAL (agreement.py)                          │   │  │
│  │  │  • Direction score: [-1, +1]                            │   │  │
│  │  │  • Strength: [0, 1]                                     │   │  │
│  │  │  • Confidence: [0, 1]                                   │   │  │
│  │  │  • Rationale: ["1h_strong_bullish", ...]               │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                             │                                            │
│                             v                                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  MULTI-HORIZON CONSENSUS (agreement.py)                          │  │
│  │  • Weighted average (longer horizons weighted more)              │  │
│  │  • Agreement score (conflict detection)                          │  │
│  │  • Rationale: ["strong_agreement", "majority_bullish", ...]      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                             │                                            │
│                             v                                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  STATE MAPPING (states.py)                                       │  │
│  │  • Direction ≥ 0.65 → STRONG_BUY                                │  │
│  │  • Direction ≥ 0.20 → BUY                                        │  │
│  │  • Direction in [-0.20, 0.20] → NEUTRAL                          │  │
│  │  • Direction ≤ -0.20 → SELL                                      │  │
│  │  • Direction ≤ -0.65 → STRONG_SELL                              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                             │                                            │
│                             v                                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  TRADE PLANNING (trade_plan.py)                                  │  │
│  │  • Entry: current close                                          │  │
│  │  • Invalidation (stop-loss):                                     │  │
│  │    - BUY: swing low - 2% buffer                                  │  │
│  │    - SELL: swing high + 2% buffer                                │  │
│  │  • Validity window: horizon-specific (5m→1h, 1d→5days)          │  │
│  │  • Size suggestion: confidence-based (0.25%-2.0%)                │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                             │                                            │
│                             v                                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  SIGNAL RESPONSE (JSON)                                          │  │
│  │  {                                                               │  │
│  │    "symbol": "BTCUSDT",                                          │  │
│  │    "state": "BUY",                                               │  │
│  │    "confidence": 0.72,                                           │  │
│  │    "trade_plan": {...},                                          │  │
│  │    "consensus": {...},                                           │  │
│  │    "horizon_details": [...]                                      │  │
│  │  }                                                               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Structures Flow

```
Bar (Phase 1)
  ↓
FeatureSet (per horizon)
  ├── n_bars: int
  ├── momentum: float
  ├── volatility: float
  ├── trend_direction: float
  ├── stability: float
  └── ...
  ↓
HorizonSignal (per horizon)
  ├── horizon: str
  ├── direction_score: float [-1, +1]
  ├── strength: float [0, 1]
  ├── confidence: float [0, 1]
  ├── features: FeatureSet
  └── rationale: list[str]
  ↓
ConsensusSignal (aggregated)
  ├── consensus_direction: float [-1, +1]
  ├── consensus_confidence: float [0, 1]
  ├── agreement_score: float [0, 1]
  ├── horizon_signals: list[HorizonSignal]
  └── rationale: list[str]
  ↓
SignalState (discrete)
  └── STRONG_BUY | BUY | NEUTRAL | SELL | STRONG_SELL
  ↓
TradePlan (actionable)
  ├── state: SignalState
  ├── confidence: float
  ├── entry_price: float
  ├── invalidation_price: float
  ├── valid_until_ts: int
  ├── size_suggestion_pct: float
  └── rationale: list[str]
  ↓
SignalResponse (API output)
  ├── symbol: str
  ├── state: str
  ├── confidence: float
  ├── trade_plan: dict
  ├── consensus: dict
  └── horizon_details: list[dict]
```

---

## Module Dependencies

```
main.py (FastAPI)
  ↓ includes
api/signals.py (router)
  ↓ calls
signals/engine.py (orchestrator)
  ↓ uses
  ├── agreement.py
  │   ├── features.py
  │   └── confidence.py
  ├── states.py
  └── trade_plan.py
  ↓ returns
types.py (data structures)
  ↓ configured by
config.py (constants)
```

---

## Timeframe Weighting Example

```
Input: Multi-horizon bars for BTCUSDT

Horizon Signals:
┌─────────┬───────────┬────────────┬────────┐
│ Horizon │ Direction │ Confidence │ Weight │
├─────────┼───────────┼────────────┼────────┤
│ 1m      │ +0.3      │ 0.6        │ 0.5    │ Effective: 0.3 * 0.6 * 0.5 = 0.09
│ 5m      │ +0.4      │ 0.7        │ 0.8    │ Effective: 0.4 * 0.7 * 0.8 = 0.224
│ 15m     │ +0.5      │ 0.75       │ 1.0    │ Effective: 0.5 * 0.75 * 1.0 = 0.375
│ 1h      │ +0.6      │ 0.8        │ 1.5    │ Effective: 0.6 * 0.8 * 1.5 = 0.72
│ 4h      │ +0.7      │ 0.85       │ 2.0    │ Effective: 0.7 * 0.85 * 2.0 = 1.19
│ 1d      │ +0.8      │ 0.9        │ 2.5    │ Effective: 0.8 * 0.9 * 2.5 = 1.8
└─────────┴───────────┴────────────┴────────┘

Total weight: 0.09 + 0.224 + 0.375 + 0.72 + 1.19 + 1.8 = 4.399
Consensus direction: 4.399 / (0.3 + 0.56 + 0.75 + 1.2 + 1.7 + 2.25) = 0.64

Result: BUY (just below STRONG_BUY threshold of 0.65)
```

---

## Conflict Detection Example

```
Short-term (1m, 5m): Bullish (+0.5)
Long-term (1d): Bearish (-0.6)

Consensus: Weighted average ≈ -0.1 (NEUTRAL)
Agreement Score: 0.45 (LOW)

Rationale tags:
- "conflicting_signals"
- "short_term_bullish_long_term_bearish"
- "weak_agreement"
- "mixed_directions"

→ User sees warning: conflicting signals, proceed with caution
```

---

## Position Sizing Logic

```
Confidence → Size Suggestion

 1.0 ┤                               ┌─────── 2.0%
     │                           ┌───┘
 0.9 ┤                       ┌───┘
     │                   ┌───┘        1.5%
 0.75┤               ┌───┘
     │           ┌───┘                1.0%
 0.6 ┤       ┌───┘
     │   ┌───┘                        0.5%
 0.4 ┤───┘
     │                                0.25%
 0.0 └─────────────────────────────────────→
                                     Position Size

Conservative by default, scales with confidence
```

---

## API Integration Points

```
┌─────────────────┐
│  External UI    │ (Streamlit, custom frontend, trading bot)
└────────┬────────┘
         │ HTTP
         v
┌─────────────────────────────────────────┐
│  FastAPI Core API (main.py)             │
│                                         │
│  Phase 1 Endpoints:                     │
│  • GET /v1/bars                         │
│  • POST /v1/forecast                    │
│  • GET /v1/providers                    │
│                                         │
│  Phase 2 Endpoint:                      │
│  • POST /v1/signal ← NEW                │
│  • GET /v1/signal/schema                │
└─────────────────────────────────────────┘
         │
         v
┌─────────────────┐
│  SQLite Store   │ (Phase 1 data)
└─────────────────┘
```

---

## Testing Pyramid

```
                    ┌─────────────┐
                    │ Integration │ (4 tests)
                    │  test_engine│
                    └─────────────┘
                          │
                          v
        ┌──────────────────────────────────┐
        │     Component Tests              │ (47 tests)
        │  test_confidence                 │
        │  test_features                   │
        │  test_agreement                  │
        │  test_states                     │
        │  test_trade_plan                 │
        └──────────────────────────────────┘
                          │
                          v
        ┌──────────────────────────────────┐
        │     Unit Tests                   │ (10 tests)
        │  compute_direction_score         │
        │  compute_strength                │
        │  get_size_suggestion             │
        │  compute_agreement_score         │
        └──────────────────────────────────┘

Total: 61 tests ✅ (100% pass rate)
```

---

## Performance Characteristics

### Latency (per signal generation):
- **Bar fetching**: 10-50ms (SQLite query)
- **Feature extraction**: 1-5ms per horizon
- **Consensus computation**: <1ms
- **Trade planning**: <1ms
- **Total**: ~50-100ms for 6 horizons

### Scalability:
- **Symbols**: Independent (no cross-symbol dependencies)
- **Horizons**: Linear scaling (6 horizons = 6x feature extraction)
- **Bars**: Linear with bar_limit (100 bars is fast)
- **Bottleneck**: SQLite queries (Phase 1)

### Memory:
- **Per request**: ~1-2 MB (100 bars × 6 horizons)
- **No caching**: Stateless (could add caching)

---

## Extension Points

### 1. Add New Features
Edit `signals/features.py`:
```python
def extract_features(horizon, bars):
    # Add new feature:
    rsi = compute_rsi(bars, period=14)
    return FeatureSet(..., rsi=rsi)
```

### 2. Change Thresholds
Edit `signals/config.py`:
```python
STRONG_BUY_THRESHOLD = 0.70  # Make stricter
```

### 3. Add New Horizon
```python
DEFAULT_HORIZONS = [..., "1w"]  # Add weekly
HORIZON_WEIGHTS["1w"] = 3.0
```

### 4. Custom Sizing Logic
Edit `signals/trade_plan.py`:
```python
def get_size_suggestion(confidence):
    # Custom ATR-based sizing
    return compute_atr_sizing(confidence)
```

### 5. ML Integration (Future)
Replace `features.extract_features()` with:
```python
def extract_features(horizon, bars):
    # Call ML model for predictions
    predictions = ml_model.predict(bars)
    return FeatureSet(momentum=predictions['momentum'], ...)
```

---

**Architecture Document Version**: 2.0.0  
**Phase 2 Status**: Production-ready ✅  
**Last Updated**: January 2026

