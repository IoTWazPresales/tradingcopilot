"""Multi-horizon signal agreement and consensus."""

from __future__ import annotations

from typing import Any

from .config import HORIZON_WEIGHTS
from .confidence import compute_confidence, compute_continuity_score
from .features import compute_direction_score, compute_strength, extract_features
from .types import ConsensusSignal, HorizonSignal


def compute_horizon_signal(
    horizon: str,
    bars: list[dict[str, Any]],
) -> HorizonSignal:
    """
    Compute signal for a single horizon.
    
    Args:
        horizon: Timeframe identifier (e.g., "1m", "1h")
        bars: List of bar dictionaries for this horizon (oldest first)
        
    Returns:
        HorizonSignal with direction, strength, confidence, and rationale
    """
    # Extract features
    features = extract_features(horizon, bars)
    
    # Compute direction and strength
    direction_score = compute_direction_score(features)
    strength = compute_strength(features)
    
    # Compute confidence
    continuity = compute_continuity_score(bars)
    confidence = compute_confidence(
        horizon=horizon,
        n_bars=features.n_bars,
        continuity_score=continuity,
        volatility=features.volatility,
    )
    
    # Build rationale tags
    rationale = []
    
    # Direction tags
    if direction_score > 0.5:
        rationale.append(f"{horizon}_strong_bullish")
    elif direction_score > 0.1:
        rationale.append(f"{horizon}_weak_bullish")
    elif direction_score < -0.5:
        rationale.append(f"{horizon}_strong_bearish")
    elif direction_score < -0.1:
        rationale.append(f"{horizon}_weak_bearish")
    else:
        rationale.append(f"{horizon}_neutral")
    
    # Volatility tags
    if features.volatility > 0.05:
        rationale.append(f"{horizon}_high_volatility")
    elif features.volatility < 0.01:
        rationale.append(f"{horizon}_low_volatility")
    
    # Confidence tags
    if confidence > 0.7:
        rationale.append(f"{horizon}_high_confidence")
    elif confidence < 0.3:
        rationale.append(f"{horizon}_low_confidence")
    
    return HorizonSignal(
        horizon=horizon,
        direction_score=direction_score,
        strength=strength,
        confidence=confidence,
        features=features,
        rationale=rationale,
    )


def compute_consensus(horizon_signals: list[HorizonSignal]) -> ConsensusSignal:
    """
    Compute consensus from multiple horizon signals.
    
    Longer horizons are weighted more heavily. Conflicts penalize confidence.
    
    Args:
        horizon_signals: List of HorizonSignal objects
        
    Returns:
        ConsensusSignal with weighted consensus and agreement metrics
    """
    if not horizon_signals:
        # No signals - return neutral
        return ConsensusSignal(
            consensus_direction=0.0,
            consensus_confidence=0.0,
            agreement_score=0.0,
            horizon_signals=[],
            rationale=["no_data"],
        )
    
    # Compute weighted average direction
    total_weight = 0.0
    weighted_direction = 0.0
    
    for signal in horizon_signals:
        weight = HORIZON_WEIGHTS.get(signal.horizon, 1.0)
        # Weight by both horizon importance and signal confidence
        effective_weight = weight * signal.confidence
        weighted_direction += signal.direction_score * effective_weight
        total_weight += effective_weight
    
    if total_weight > 0:
        consensus_direction = weighted_direction / total_weight
    else:
        consensus_direction = 0.0
    
    # Compute agreement score (how well horizons align)
    agreement_score = compute_agreement_score(horizon_signals, consensus_direction)
    
    # Compute consensus confidence (average confidence with agreement penalty)
    avg_confidence = sum(s.confidence for s in horizon_signals) / len(horizon_signals)
    consensus_confidence = avg_confidence * agreement_score
    
    # Build rationale
    rationale = build_consensus_rationale(horizon_signals, agreement_score)
    
    return ConsensusSignal(
        consensus_direction=consensus_direction,
        consensus_confidence=consensus_confidence,
        agreement_score=agreement_score,
        horizon_signals=horizon_signals,
        rationale=rationale,
    )


def compute_agreement_score(
    horizon_signals: list[HorizonSignal],
    consensus_direction: float,
) -> float:
    """
    Compute how well horizon signals agree [0, 1].
    
    Higher score = better agreement. Conflicts reduce score.
    
    Args:
        horizon_signals: List of horizon signals
        consensus_direction: The computed consensus direction
        
    Returns:
        Agreement score [0, 1]
    """
    if not horizon_signals:
        return 1.0
    
    # Measure deviation from consensus
    deviations = []
    for signal in horizon_signals:
        # Absolute difference from consensus
        deviation = abs(signal.direction_score - consensus_direction)
        deviations.append(deviation)
    
    # Average deviation
    avg_deviation = sum(deviations) / len(deviations)
    
    # Convert to agreement score (inverse of deviation)
    # Max deviation is 2.0 (one at -1, one at +1)
    agreement = 1.0 - (avg_deviation / 2.0)
    
    return max(0.0, min(1.0, agreement))


def build_consensus_rationale(
    horizon_signals: list[HorizonSignal],
    agreement_score: float,
) -> list[str]:
    """
    Build rationale tags for consensus signal.
    
    Args:
        horizon_signals: List of horizon signals
        agreement_score: Agreement metric [0, 1]
        
    Returns:
        List of rationale tags
    """
    rationale = []
    
    # Count bullish vs bearish horizons
    bullish_count = sum(1 for s in horizon_signals if s.direction_score > 0.1)
    bearish_count = sum(1 for s in horizon_signals if s.direction_score < -0.1)
    neutral_count = len(horizon_signals) - bullish_count - bearish_count
    
    # Agreement tags
    if agreement_score > 0.8:
        rationale.append("strong_agreement")
    elif agreement_score > 0.6:
        rationale.append("moderate_agreement")
    elif agreement_score < 0.4:
        rationale.append("weak_agreement")
        rationale.append("conflicting_signals")
    
    # Directional consensus tags
    if bullish_count > bearish_count * 2:
        rationale.append("majority_bullish")
    elif bearish_count > bullish_count * 2:
        rationale.append("majority_bearish")
    elif bullish_count > 0 and bearish_count > 0:
        rationale.append("mixed_directions")
    
    # Specific conflict patterns
    if bullish_count > 0 and bearish_count > 0:
        # Check short vs long term
        short_term = [s for s in horizon_signals if s.horizon in ["1m", "5m", "15m"]]
        long_term = [s for s in horizon_signals if s.horizon in ["1h", "4h", "1d", "1w"]]
        
        if short_term and long_term:
            short_avg = sum(s.direction_score for s in short_term) / len(short_term)
            long_avg = sum(s.direction_score for s in long_term) / len(long_term)
            
            if short_avg > 0.2 and long_avg < -0.2:
                rationale.append("short_term_bullish_long_term_bearish")
            elif short_avg < -0.2 and long_avg > 0.2:
                rationale.append("short_term_bearish_long_term_bullish")
    
    # Confidence tags
    avg_conf = sum(s.confidence for s in horizon_signals) / len(horizon_signals)
    if avg_conf > 0.7:
        rationale.append("high_data_quality")
    elif avg_conf < 0.3:
        rationale.append("low_data_quality")
    
    return rationale

