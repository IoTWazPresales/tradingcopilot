"""Feature extraction from OHLCV bars."""

from __future__ import annotations

import math
from typing import Any

from .config import MOMENTUM_LOOKBACK, VOLATILITY_LOOKBACK
from .types import FeatureSet


def extract_features(horizon: str, bars: list[dict[str, Any]]) -> FeatureSet:
    """
    Extract deterministic features from bars for a single horizon.
    
    Args:
        horizon: Timeframe identifier (e.g., "1m", "1h")
        bars: List of bar dictionaries (oldest first, newest last)
        
    Returns:
        FeatureSet with computed features
    """
    n_bars = len(bars)
    
    if n_bars == 0:
        # No data - return neutral features
        return FeatureSet(
            horizon=horizon,
            n_bars=0,
            momentum=0.0,
            volatility=0.0,
            trend_direction=0.0,
            stability=0.0,
            last_close=0.0,
            first_close=0.0,
            avg_range=0.0,
        )
    
    closes = [float(b["close"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    
    last_close = closes[-1]
    first_close = closes[0]
    
    # Momentum: return over lookback window (normalized to [-1, +1])
    momentum_lookback = min(MOMENTUM_LOOKBACK, n_bars)
    if momentum_lookback > 1:
        start_price = closes[-momentum_lookback]
        momentum_return = (last_close - start_price) / max(1e-9, start_price)
        # Normalize with tanh to bound to [-1, +1]
        momentum = math.tanh(momentum_return * 10.0)  # Scale for sensitivity
    else:
        momentum = 0.0
    
    # Volatility: standard deviation of returns
    volatility_lookback = min(VOLATILITY_LOOKBACK, n_bars - 1)
    if volatility_lookback > 1:
        returns = []
        for i in range(len(closes) - volatility_lookback, len(closes)):
            if i > 0:
                ret = (closes[i] - closes[i - 1]) / max(1e-9, closes[i - 1])
                returns.append(ret)
        
        if returns:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / max(1, len(returns) - 1)
            volatility = math.sqrt(max(0.0, variance))
        else:
            volatility = 0.0
    else:
        volatility = 0.0
    
    # Trend direction: sign of momentum
    if momentum > 0.1:
        trend_direction = 1.0
    elif momentum < -0.1:
        trend_direction = -1.0
    else:
        trend_direction = 0.0
    
    # Stability: inverse volatility (signal-to-noise ratio)
    if volatility > 0:
        stability = 1.0 / (1.0 + volatility * 20.0)  # Scaled inverse
    else:
        stability = 1.0
    
    # Average range (high - low)
    ranges = [highs[i] - lows[i] for i in range(n_bars)]
    avg_range = sum(ranges) / n_bars if ranges else 0.0
    
    return FeatureSet(
        horizon=horizon,
        n_bars=n_bars,
        momentum=momentum,
        volatility=volatility,
        trend_direction=trend_direction,
        stability=stability,
        last_close=last_close,
        first_close=first_close,
        avg_range=avg_range,
    )


def compute_direction_score(features: FeatureSet) -> float:
    """
    Compute directional score [-1, +1] from features.
    
    Combines momentum and stability to determine bullish/bearish bias.
    
    Args:
        features: Extracted features
        
    Returns:
        Direction score: -1 (bearish) to +1 (bullish)
    """
    # Base score is momentum
    direction = features.momentum
    
    # Adjust by stability (low stability reduces conviction)
    direction *= features.stability
    
    # Clamp to [-1, +1]
    return max(-1.0, min(1.0, direction))


def compute_strength(features: FeatureSet) -> float:
    """
    Compute signal strength [0, 1] from features.
    
    Strength indicates how strong the directional bias is, regardless of direction.
    
    Args:
        features: Extracted features
        
    Returns:
        Strength score [0, 1]
    """
    # Strength is absolute momentum weighted by stability
    strength = abs(features.momentum) * features.stability
    
    # Clamp to [0, 1]
    return max(0.0, min(1.0, strength))

