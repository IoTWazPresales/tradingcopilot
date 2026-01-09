"""Phase 2 configuration constants."""

from __future__ import annotations


# Horizon analysis configuration
DEFAULT_HORIZONS = ["1m", "5m", "15m", "1h", "4h", "1d"]

# Expected bars for "good enough" confidence per horizon
EXPECTED_BARS = {
    "1m": 60,    # 1 hour
    "5m": 60,    # 5 hours
    "15m": 60,   # 15 hours
    "1h": 48,    # 2 days
    "4h": 42,    # 1 week
    "1d": 30,    # 1 month
    "1w": 26,    # 6 months
}

# Horizon weights for consensus (longer = more weight)
HORIZON_WEIGHTS = {
    "1m": 0.5,
    "5m": 0.7,
    "15m": 1.0,
    "1h": 1.5,
    "4h": 2.0,
    "1d": 2.5,
    "1w": 3.0,
}

# Confidence thresholds (NOT hard cutoffs, but used for smooth functions)
MIN_BARS_FOR_NONZERO = 10  # Below this, confidence approaches 0
CONTINUITY_PENALTY_PER_GAP = 0.05  # Reduce confidence by this per detected gap

# Volatility normalization (for confidence penalty)
VOLATILITY_THRESHOLD_LOW = 0.01  # Below = stable
VOLATILITY_THRESHOLD_HIGH = 0.05  # Above = unstable

# Signal state thresholds
STRONG_BUY_THRESHOLD = 0.65
BUY_THRESHOLD = 0.20
NEUTRAL_THRESHOLD = 0.20  # -NEUTRAL_THRESHOLD to +NEUTRAL_THRESHOLD = NEUTRAL
SELL_THRESHOLD = -0.20
STRONG_SELL_THRESHOLD = -0.65

# Trade plan configuration
INVALIDATION_BUFFER_PCT = 0.02  # 2% beyond swing for stop loss
VALIDITY_WINDOW_MULTIPLIER = {
    "1m": 30 * 60,      # 30 minutes
    "5m": 2 * 3600,     # 2 hours
    "15m": 4 * 3600,    # 4 hours
    "1h": 8 * 3600,     # 8 hours
    "4h": 24 * 3600,    # 1 day
    "1d": 5 * 24 * 3600,  # 5 days
    "1w": 2 * 7 * 24 * 3600,  # 2 weeks
}

# Size suggestions by confidence bands (% of capital)
SIZE_BY_CONFIDENCE = [
    (0.0, 0.3, 0.25),   # Low confidence: 0.25%
    (0.3, 0.5, 0.5),    # Medium-low: 0.5%
    (0.5, 0.7, 1.0),    # Medium: 1%
    (0.7, 0.85, 1.5),   # High: 1.5%
    (0.85, 1.0, 2.0),   # Very high: 2%
]

# Feature extraction lookbacks
MOMENTUM_LOOKBACK = 10  # Use last N bars for momentum calculation
VOLATILITY_LOOKBACK = 20  # Use last N bars for volatility

