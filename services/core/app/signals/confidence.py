"""Adaptive confidence scoring for horizon signals."""

from __future__ import annotations

import math
from typing import Any

from .config import (
    CONTINUITY_PENALTY_PER_GAP,
    EXPECTED_BARS,
    MIN_BARS_FOR_NONZERO,
    VOLATILITY_THRESHOLD_HIGH,
    VOLATILITY_THRESHOLD_LOW,
)


def compute_confidence(
    horizon: str,
    n_bars: int,
    continuity_score: float,
    volatility: float,
) -> float:
    """
    Compute adaptive confidence score [0, 1] for a horizon.
    
    Confidence increases smoothly with:
    - More bars available (relative to expected)
    - Better continuity (fewer gaps, monotonic timestamps)
    - Lower volatility (more stable data)
    
    Args:
        horizon: Timeframe identifier (e.g., "1m", "1h")
        n_bars: Number of bars available
        continuity_score: [0, 1] where 1 = perfect continuity, 0 = very gappy
        volatility: Std of returns or similar proxy
        
    Returns:
        Confidence score [0, 1]
    """
    # Component 1: Data sufficiency (sigmoid curve)
    expected = EXPECTED_BARS.get(horizon, 60)
    if n_bars < MIN_BARS_FOR_NONZERO:
        data_score = 0.01  # Near zero but not exactly zero
    else:
        # Sigmoid: approaches 1 as n_bars approaches 2*expected
        x = (n_bars - MIN_BARS_FOR_NONZERO) / (expected - MIN_BARS_FOR_NONZERO)
        data_score = 1.0 / (1.0 + math.exp(-3.0 * (x - 1.0)))  # Centered at x=1
        data_score = max(0.01, min(1.0, data_score))
    
    # Component 2: Continuity (linear penalty)
    continuity_component = max(0.1, continuity_score)  # Floor at 0.1
    
    # Component 3: Volatility penalty (piecewise linear)
    if volatility < VOLATILITY_THRESHOLD_LOW:
        volatility_component = 1.0  # Stable
    elif volatility > VOLATILITY_THRESHOLD_HIGH:
        # High volatility: penalize heavily
        excess = volatility - VOLATILITY_THRESHOLD_HIGH
        penalty = min(0.5, excess * 10.0)  # Up to 50% penalty
        volatility_component = max(0.5, 1.0 - penalty)
    else:
        # Medium volatility: linear interpolation
        ratio = (volatility - VOLATILITY_THRESHOLD_LOW) / (
            VOLATILITY_THRESHOLD_HIGH - VOLATILITY_THRESHOLD_LOW
        )
        volatility_component = 1.0 - (ratio * 0.3)  # Up to 30% penalty
    
    # Combine components (geometric mean for balance)
    confidence = (data_score * continuity_component * volatility_component) ** (1.0 / 3.0)
    
    return max(0.0, min(1.0, confidence))


def compute_continuity_score(bars: list[dict[str, Any]]) -> float:
    """
    Compute continuity score [0, 1] based on timestamp gaps.
    
    Args:
        bars: List of bar dictionaries with 'ts' field
        
    Returns:
        Continuity score: 1.0 = perfect, 0.0 = very gappy
    """
    if len(bars) < 2:
        return 1.0  # Too few bars to assess
    
    timestamps = [b["ts"] for b in bars]
    
    # Check monotonic increasing
    if timestamps != sorted(timestamps):
        return 0.5  # Non-monotonic is suspicious
    
    # Detect expected interval from first two bars
    expected_interval = timestamps[1] - timestamps[0]
    if expected_interval <= 0:
        return 0.3  # Invalid interval
    
    # Count gaps (where actual interval > expected * 1.5)
    gaps = 0
    for i in range(1, len(timestamps)):
        actual_interval = timestamps[i] - timestamps[i - 1]
        if actual_interval > expected_interval * 1.5:
            gaps += 1
    
    # Penalty per gap
    penalty = gaps * CONTINUITY_PENALTY_PER_GAP
    score = max(0.0, 1.0 - penalty)
    
    return score

