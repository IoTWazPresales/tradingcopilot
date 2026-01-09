"""Trade plan generation from signals and bars."""

from __future__ import annotations

import time
from typing import Any

from .config import INVALIDATION_BUFFER_PCT, SIZE_BY_CONFIDENCE, VALIDITY_WINDOW_MULTIPLIER
from .types import ConsensusSignal, SignalState, TradePlan


def generate_trade_plan(
    symbol: str,
    state: SignalState,
    confidence: float,
    consensus: ConsensusSignal,
    bars_1m: list[dict[str, Any]],
    rationale: list[str],
) -> TradePlan:
    """
    Generate actionable trade plan from signal state and bars.
    
    Args:
        symbol: Trading symbol
        state: Discrete signal state
        confidence: Final confidence [0, 1]
        consensus: ConsensusSignal for context
        bars_1m: Recent 1m bars for swing detection
        rationale: Existing rationale tags
        
    Returns:
        TradePlan with entry, invalidation, timing, and size
    """
    current_ts = int(time.time())
    
    # Get latest price
    if bars_1m:
        last_close = float(bars_1m[-1]["close"])
    else:
        last_close = 0.0
    
    # Determine entry price
    entry_price = last_close  # Market entry for now (deterministic)
    
    # Determine invalidation based on state
    if state in [SignalState.BUY, SignalState.STRONG_BUY]:
        invalidation_price = compute_buy_invalidation(bars_1m, last_close)
        rationale_copy = rationale + ["long_position"]
    elif state in [SignalState.SELL, SignalState.STRONG_SELL]:
        invalidation_price = compute_sell_invalidation(bars_1m, last_close)
        rationale_copy = rationale + ["short_position"]
    else:
        # NEUTRAL - no trade
        invalidation_price = last_close  # No invalidation needed
        rationale_copy = rationale + ["no_position_neutral"]
    
    # Determine validity window
    # Use primary horizon (highest weighted with data)
    if consensus.horizon_signals:
        primary_horizon = max(
            consensus.horizon_signals,
            key=lambda s: s.confidence
        ).horizon
    else:
        primary_horizon = "1h"  # Default
    
    validity_seconds = VALIDITY_WINDOW_MULTIPLIER.get(primary_horizon, 3600)
    valid_until_ts = current_ts + validity_seconds
    
    # Determine size suggestion based on confidence
    size_pct = get_size_suggestion(confidence)
    
    # Add size rationale
    if size_pct <= 0.5:
        rationale_copy.append("conservative_sizing")
    elif size_pct >= 1.5:
        rationale_copy.append("aggressive_sizing")
    
    return TradePlan(
        state=state,
        confidence=confidence,
        entry_price=entry_price if state != SignalState.NEUTRAL else None,
        invalidation_price=invalidation_price,
        valid_until_ts=valid_until_ts,
        size_suggestion_pct=size_pct,
        rationale=rationale_copy,
        symbol=symbol,
        as_of_ts=current_ts,
        horizons_analyzed=[s.horizon for s in consensus.horizon_signals],
    )


def compute_buy_invalidation(bars: list[dict[str, Any]], current_price: float) -> float:
    """
    Compute invalidation (stop-loss) for BUY signal.
    
    Uses recent swing low minus buffer.
    
    Args:
        bars: Recent bars (1m recommended)
        current_price: Current close price
        
    Returns:
        Invalidation price (below current)
    """
    if not bars:
        return current_price * (1.0 - INVALIDATION_BUFFER_PCT)
    
    # Look back at most recent 20 bars for swing low
    lookback = min(20, len(bars))
    recent_bars = bars[-lookback:]
    
    # Find swing low (minimum low)
    swing_low = min(float(b["low"]) for b in recent_bars)
    
    # Apply buffer below swing low
    invalidation = swing_low * (1.0 - INVALIDATION_BUFFER_PCT)
    
    # Ensure it's below current price
    if invalidation >= current_price:
        invalidation = current_price * (1.0 - INVALIDATION_BUFFER_PCT)
    
    return invalidation


def compute_sell_invalidation(bars: list[dict[str, Any]], current_price: float) -> float:
    """
    Compute invalidation (stop-loss) for SELL signal.
    
    Uses recent swing high plus buffer.
    
    Args:
        bars: Recent bars (1m recommended)
        current_price: Current close price
        
    Returns:
        Invalidation price (above current)
    """
    if not bars:
        return current_price * (1.0 + INVALIDATION_BUFFER_PCT)
    
    # Look back at most recent 20 bars for swing high
    lookback = min(20, len(bars))
    recent_bars = bars[-lookback:]
    
    # Find swing high (maximum high)
    swing_high = max(float(b["high"]) for b in recent_bars)
    
    # Apply buffer above swing high
    invalidation = swing_high * (1.0 + INVALIDATION_BUFFER_PCT)
    
    # Ensure it's above current price
    if invalidation <= current_price:
        invalidation = current_price * (1.0 + INVALIDATION_BUFFER_PCT)
    
    return invalidation


def get_size_suggestion(confidence: float) -> float:
    """
    Get position size suggestion based on confidence.
    
    Uses confidence bands from config.
    
    Args:
        confidence: Confidence score [0, 1]
        
    Returns:
        Suggested size as % of capital
    """
    for low, high, size in SIZE_BY_CONFIDENCE:
        if low <= confidence < high:
            return size
    
    # Fallback (should not reach here if bands cover [0, 1])
    return 0.25

