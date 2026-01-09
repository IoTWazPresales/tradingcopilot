"""Map consensus signal to discrete states."""

from __future__ import annotations

from .config import (
    BUY_THRESHOLD,
    NEUTRAL_THRESHOLD,
    SELL_THRESHOLD,
    STRONG_BUY_THRESHOLD,
    STRONG_SELL_THRESHOLD,
)
from .types import ConsensusSignal, SignalState


def map_to_signal_state(consensus: ConsensusSignal) -> tuple[SignalState, list[str]]:
    """
    Map consensus direction to discrete signal state.
    
    Uses deterministic thresholds. Returns state and rationale tags.
    
    Args:
        consensus: ConsensusSignal with direction and confidence
        
    Returns:
        Tuple of (SignalState, rationale_tags)
    """
    direction = consensus.consensus_direction
    rationale = list(consensus.rationale)  # Copy to avoid mutation
    
    # Map direction to state
    if direction >= STRONG_BUY_THRESHOLD:
        state = SignalState.STRONG_BUY
        rationale.append("signal_strong_buy")
    elif direction >= BUY_THRESHOLD:
        state = SignalState.BUY
        rationale.append("signal_buy")
    elif direction <= STRONG_SELL_THRESHOLD:
        state = SignalState.STRONG_SELL
        rationale.append("signal_strong_sell")
    elif direction <= SELL_THRESHOLD:
        state = SignalState.SELL
        rationale.append("signal_sell")
    else:
        # Between -NEUTRAL_THRESHOLD and +NEUTRAL_THRESHOLD
        state = SignalState.NEUTRAL
        rationale.append("signal_neutral")
    
    # Add confidence qualifiers
    confidence = consensus.consensus_confidence
    if confidence > 0.7:
        rationale.append("high_confidence_signal")
    elif confidence < 0.3:
        rationale.append("low_confidence_signal")
    
    # Add agreement qualifiers
    if consensus.agreement_score < 0.5:
        rationale.append("low_agreement_warning")
    
    return state, rationale

