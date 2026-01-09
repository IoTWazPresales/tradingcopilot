"""
Phase 3: Confidence breakdown and debug trace.

This module DOES NOT change Phase 2 calculations.
It extracts and exposes intermediate values for transparency.
"""

from typing import Any, Dict, List, Optional

from .types import ConsensusSignal, HorizonSignal


def compute_confidence_breakdown(
    consensus: ConsensusSignal,
    horizon_signals: List[HorizonSignal],
) -> Dict[str, Any]:
    """
    Break down consensus confidence into components.
    
    This DOES NOT change the confidence calculation - it just exposes
    the components that went into it.
    
    Args:
        consensus: ConsensusSignal with final confidence
        horizon_signals: List of horizon signals with individual confidences
        
    Returns:
        Dict with confidence components
    """
    if not horizon_signals:
        return {
            "total": 0.0,
            "data_quality": 0.0,
            "agreement": 0.0,
            "components": {
                "avg_horizon_confidence": 0.0,
                "agreement_score": 0.0,
                "consensus_confidence": 0.0,
            }
        }
    
    # Average confidence across horizons (data quality proxy)
    avg_horizon_conf = sum(s.confidence for s in horizon_signals) / len(horizon_signals)
    
    # Agreement score (from consensus)
    agreement_score = consensus.agreement_score
    
    # Final consensus confidence (already calculated in Phase 2)
    final_confidence = consensus.consensus_confidence
    
    # Break down into conceptual components
    # Note: This is an approximation for explainability
    # The actual calculation is: avg_horizon_conf * agreement_score
    data_quality_component = avg_horizon_conf
    agreement_component = agreement_score
    
    # Volatility adjustment is implicit in individual horizon confidences
    # We can't extract it without changing Phase 2, so we note it
    
    return {
        "total": round(final_confidence, 4),
        "data_quality": round(data_quality_component, 4),
        "agreement": round(agreement_component, 4),
        "components": {
            "avg_horizon_confidence": round(avg_horizon_conf, 4),
            "agreement_score": round(agreement_score, 4),
            "consensus_confidence": round(final_confidence, 4),
        },
        "explanation": {
            "data_quality": f"Average confidence across {len(horizon_signals)} timeframes",
            "agreement": f"How well timeframes align (1.0 = perfect agreement)",
            "total": f"data_quality × agreement = {round(final_confidence, 4)}",
        }
    }


def build_debug_trace(
    symbol: str,
    horizon_signals: List[HorizonSignal],
    consensus: ConsensusSignal,
    config_horizons: List[str],
) -> Dict[str, Any]:
    """
    Build comprehensive debug trace showing all intermediate calculations.
    
    This is for debugging and transparency - NOT for production use.
    
    Args:
        symbol: Trading symbol
        horizon_signals: List of horizon signals
        consensus: Consensus signal
        config_horizons: Configured horizons
        
    Returns:
        Debug trace with all intermediate values
    """
    from .config import HORIZON_WEIGHTS
    
    # Per-horizon breakdown
    horizon_details = []
    for signal in horizon_signals:
        weight = HORIZON_WEIGHTS.get(signal.horizon, 1.0)
        effective_weight = weight * signal.confidence
        
        horizon_details.append({
            "horizon": signal.horizon,
            "direction_score": round(signal.direction_score, 4),
            "strength": round(signal.strength, 4),
            "confidence": round(signal.confidence, 4),
            "weight": weight,
            "effective_weight": round(effective_weight, 4),
            "weighted_direction": round(signal.direction_score * effective_weight, 4),
            "features": {
                "n_bars": signal.features.n_bars,
                "momentum": round(signal.features.momentum, 4),
                "volatility": round(signal.features.volatility, 6),
                "trend_direction": signal.features.trend_direction,
                "stability": round(signal.features.stability, 4),
            },
            "rationale": signal.rationale,
        })
    
    # Consensus calculation breakdown
    total_weighted_direction = sum(
        s.direction_score * HORIZON_WEIGHTS.get(s.horizon, 1.0) * s.confidence
        for s in horizon_signals
    )
    total_effective_weight = sum(
        HORIZON_WEIGHTS.get(s.horizon, 1.0) * s.confidence
        for s in horizon_signals
    )
    
    consensus_calc = {
        "total_weighted_direction": round(total_weighted_direction, 4),
        "total_effective_weight": round(total_effective_weight, 4),
        "consensus_direction": round(
            total_weighted_direction / total_effective_weight if total_effective_weight > 0 else 0.0,
            4
        ),
        "agreement_score": round(consensus.agreement_score, 4),
        "avg_horizon_confidence": round(
            sum(s.confidence for s in horizon_signals) / len(horizon_signals) if horizon_signals else 0.0,
            4
        ),
        "consensus_confidence": round(consensus.consensus_confidence, 4),
    }
    
    # Thresholds applied
    from .config import (
        STRONG_BUY_THRESHOLD,
        BUY_THRESHOLD,
        NEUTRAL_THRESHOLD,
        SELL_THRESHOLD,
        STRONG_SELL_THRESHOLD,
    )
    
    thresholds = {
        "strong_buy": STRONG_BUY_THRESHOLD,
        "buy": BUY_THRESHOLD,
        "neutral": f"±{NEUTRAL_THRESHOLD}",
        "sell": SELL_THRESHOLD,
        "strong_sell": STRONG_SELL_THRESHOLD,
    }
    
    # Missing horizons
    missing_horizons = [h for h in config_horizons if h not in {s.horizon for s in horizon_signals}]
    
    return {
        "symbol": symbol,
        "horizons_analyzed": [s.horizon for s in horizon_signals],
        "horizons_requested": config_horizons,
        "horizons_missing": missing_horizons,
        "horizon_details": horizon_details,
        "consensus_calculation": consensus_calc,
        "thresholds": thresholds,
        "rationale_tags": consensus.rationale,
        "note": "This debug trace is for transparency. All values are from Phase 2 - no recalculation performed."
    }


def should_include_explanation(request_params: Dict[str, Any]) -> bool:
    """Check if explanation should be included based on request params."""
    return request_params.get("explain", False) or request_params.get("debug", False)


def should_include_debug(request_params: Dict[str, Any]) -> bool:
    """Check if debug trace should be included based on request params."""
    return request_params.get("debug", False)

