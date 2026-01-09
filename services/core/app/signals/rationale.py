"""
Phase 3: Rationale taxonomy and human-readable explanation formatter.

This module DOES NOT change any Phase 2 logic or calculations.
It only translates existing rationale tags into structured explanations.
"""

from typing import Dict, List, Literal

# Rationale tag categories
RationaleCategory = Literal["driver", "risk", "note"]


# Complete taxonomy of existing rationale tags
RATIONALE_TAXONOMY: Dict[str, tuple[RationaleCategory, str]] = {
    # ===== DRIVERS (positive indicators) =====
    "strong_agreement": ("driver", "Strong alignment across multiple timeframes"),
    "moderate_agreement": ("driver", "Moderate agreement between analyzed timeframes"),
    "majority_bullish": ("driver", "Majority of timeframes show bullish bias"),
    "majority_bearish": ("driver", "Majority of timeframes show bearish bias"),
    "high_confidence_signal": ("driver", "High confidence due to quality data and clear trend"),
    "high_data_quality": ("driver", "Excellent data quality with minimal gaps"),
    
    # Horizon-specific drivers (bullish)
    "1m_strong_bullish": ("driver", "1-minute timeframe shows strong bullish momentum"),
    "1m_weak_bullish": ("driver", "1-minute timeframe shows weak bullish bias"),
    "5m_strong_bullish": ("driver", "5-minute timeframe shows strong bullish momentum"),
    "5m_weak_bullish": ("driver", "5-minute timeframe shows weak bullish bias"),
    "15m_strong_bullish": ("driver", "15-minute timeframe shows strong bullish momentum"),
    "15m_weak_bullish": ("driver", "15-minute timeframe shows weak bullish bias"),
    "1h_strong_bullish": ("driver", "1-hour timeframe shows strong bullish momentum"),
    "1h_weak_bullish": ("driver", "1-hour timeframe shows weak bullish bias"),
    "4h_strong_bullish": ("driver", "4-hour timeframe shows strong bullish momentum"),
    "4h_weak_bullish": ("driver", "4-hour timeframe shows weak bullish bias"),
    "1d_strong_bullish": ("driver", "Daily timeframe shows strong bullish momentum"),
    "1d_weak_bullish": ("driver", "Daily timeframe shows weak bullish bias"),
    "1w_strong_bullish": ("driver", "Weekly timeframe shows strong bullish momentum"),
    "1w_weak_bullish": ("driver", "Weekly timeframe shows weak bullish bias"),
    
    # Horizon-specific drivers (bearish)
    "1m_strong_bearish": ("driver", "1-minute timeframe shows strong bearish momentum"),
    "1m_weak_bearish": ("driver", "1-minute timeframe shows weak bearish bias"),
    "5m_strong_bearish": ("driver", "5-minute timeframe shows strong bearish momentum"),
    "5m_weak_bearish": ("driver", "5-minute timeframe shows weak bearish bias"),
    "15m_strong_bearish": ("driver", "15-minute timeframe shows strong bearish momentum"),
    "15m_weak_bearish": ("driver", "15-minute timeframe shows weak bearish bias"),
    "1h_strong_bearish": ("driver", "1-hour timeframe shows strong bearish momentum"),
    "1h_weak_bearish": ("driver", "1-hour timeframe shows weak bearish bias"),
    "4h_strong_bearish": ("driver", "4-hour timeframe shows strong bearish momentum"),
    "4h_weak_bearish": ("driver", "4-hour timeframe shows weak bearish bias"),
    "1d_strong_bearish": ("driver", "Daily timeframe shows strong bearish momentum"),
    "1d_weak_bearish": ("driver", "Daily timeframe shows weak bearish bias"),
    "1w_strong_bearish": ("driver", "Weekly timeframe shows strong bearish momentum"),
    "1w_weak_bearish": ("driver", "Weekly timeframe shows weak bearish bias"),
    
    # Signal state drivers
    "signal_strong_buy": ("driver", "Signal strength exceeds strong buy threshold (≥0.65)"),
    "signal_buy": ("driver", "Signal strength exceeds buy threshold (≥0.20)"),
    "signal_strong_sell": ("driver", "Signal strength exceeds strong sell threshold (≤-0.65)"),
    "signal_sell": ("driver", "Signal strength exceeds sell threshold (≤-0.20)"),
    
    # Trade plan drivers
    "long_position": ("driver", "Buy signal suggests long position"),
    "short_position": ("driver", "Sell signal suggests short position"),
    "aggressive_sizing": ("driver", "High confidence supports larger position size"),
    
    # ===== RISKS (negative indicators / warnings) =====
    "weak_agreement": ("risk", "Weak agreement between timeframes - conflicting signals detected"),
    "conflicting_signals": ("risk", "Timeframes show conflicting directional bias"),
    "mixed_directions": ("risk", "Mixed bullish and bearish signals across horizons"),
    "short_term_bullish_long_term_bearish": ("risk", "Short-term uptrend conflicts with long-term downtrend"),
    "short_term_bearish_long_term_bullish": ("risk", "Short-term downtrend conflicts with long-term uptrend"),
    "low_confidence_signal": ("risk", "Low confidence due to data quality or uncertainty"),
    "low_data_quality": ("risk", "Limited or gappy data reduces signal reliability"),
    "low_agreement_warning": ("risk", "Low agreement between timeframes - proceed with caution"),
    "conservative_sizing": ("risk", "Low confidence suggests smaller position size"),
    
    # Horizon-specific risks (neutral)
    "1m_neutral": ("risk", "1-minute timeframe shows no clear direction"),
    "5m_neutral": ("risk", "5-minute timeframe shows no clear direction"),
    "15m_neutral": ("risk", "15-minute timeframe shows no clear direction"),
    "1h_neutral": ("risk", "1-hour timeframe shows no clear direction"),
    "4h_neutral": ("risk", "4-hour timeframe shows no clear direction"),
    "1d_neutral": ("risk", "Daily timeframe shows no clear direction"),
    "1w_neutral": ("risk", "Weekly timeframe shows no clear direction"),
    
    # Signal state neutral
    "signal_neutral": ("risk", "Signal strength within neutral range (±0.20)"),
    
    # Trade plan risks
    "no_position_neutral": ("risk", "Neutral signal - no clear trade opportunity"),
    
    # ===== NOTES (informational, non-directional) =====
    "1m_high_volatility": ("note", "1-minute timeframe experiencing high volatility"),
    "1m_low_volatility": ("note", "1-minute timeframe experiencing low volatility"),
    "5m_high_volatility": ("note", "5-minute timeframe experiencing high volatility"),
    "5m_low_volatility": ("note", "5-minute timeframe experiencing low volatility"),
    "15m_high_volatility": ("note", "15-minute timeframe experiencing high volatility"),
    "15m_low_volatility": ("note", "15-minute timeframe experiencing low volatility"),
    "1h_high_volatility": ("note", "1-hour timeframe experiencing high volatility"),
    "1h_low_volatility": ("note", "1-hour timeframe experiencing low volatility"),
    "4h_high_volatility": ("note", "4-hour timeframe experiencing high volatility"),
    "4h_low_volatility": ("note", "4-hour timeframe experiencing low volatility"),
    "1d_high_volatility": ("note", "Daily timeframe experiencing high volatility"),
    "1d_low_volatility": ("note", "Daily timeframe experiencing low volatility"),
    "1w_high_volatility": ("note", "Weekly timeframe experiencing high volatility"),
    "1w_low_volatility": ("note", "Weekly timeframe experiencing low volatility"),
    
    "1m_high_confidence": ("note", "1-minute timeframe has high confidence data"),
    "1m_low_confidence": ("note", "1-minute timeframe has low confidence data"),
    "5m_high_confidence": ("note", "5-minute timeframe has high confidence data"),
    "5m_low_confidence": ("note", "5-minute timeframe has low confidence data"),
    "15m_high_confidence": ("note", "15-minute timeframe has high confidence data"),
    "15m_low_confidence": ("note", "15-minute timeframe has low confidence data"),
    "1h_high_confidence": ("note", "1-hour timeframe has high confidence data"),
    "1h_low_confidence": ("note", "1-hour timeframe has low confidence data"),
    "4h_high_confidence": ("note", "4-hour timeframe has high confidence data"),
    "4h_low_confidence": ("note", "4-hour timeframe has low confidence data"),
    "1d_high_confidence": ("note", "Daily timeframe has high confidence data"),
    "1d_low_confidence": ("note", "Daily timeframe has low confidence data"),
    "1w_high_confidence": ("note", "Weekly timeframe has high confidence data"),
    "1w_low_confidence": ("note", "Weekly timeframe has low confidence data"),
    
    # Special cases
    "no_data": ("note", "Insufficient data available for analysis"),
    "test": ("note", "Test rationale tag"),
}


def categorize_rationale(tags: List[str]) -> Dict[str, List[str]]:
    """
    Categorize rationale tags into drivers, risks, and notes.
    
    Args:
        tags: List of rationale tags from Phase 2
        
    Returns:
        Dict with keys: drivers, risks, notes (each a list of human-readable strings)
    """
    drivers = []
    risks = []
    notes = []
    
    for tag in tags:
        if tag in RATIONALE_TAXONOMY:
            category, text = RATIONALE_TAXONOMY[tag]
            if category == "driver":
                drivers.append(text)
            elif category == "risk":
                risks.append(text)
            elif category == "note":
                notes.append(text)
        else:
            # Unknown tag - treat as note
            notes.append(f"Unknown rationale: {tag}")
    
    return {
        "drivers": drivers,
        "risks": risks,
        "notes": notes,
    }


def format_explanation(
    drivers: List[str],
    risks: List[str],
    notes: List[str],
    max_items: int = 5,
) -> str:
    """
    Format explanation into a single human-readable paragraph.
    
    Args:
        drivers: List of positive indicators
        risks: List of warnings/risks
        notes: List of observations
        max_items: Maximum items to include per category
        
    Returns:
        Formatted explanation string
    """
    parts = []
    
    if drivers:
        driver_text = "; ".join(drivers[:max_items])
        parts.append(f"Drivers: {driver_text}")
    
    if risks:
        risk_text = "; ".join(risks[:max_items])
        parts.append(f"Risks: {risk_text}")
    
    if notes and len(parts) < 2:  # Only add notes if we have space
        note_text = "; ".join(notes[:max_items])
        parts.append(f"Notes: {note_text}")
    
    return ". ".join(parts) + "." if parts else "No explanation available."


def build_explanation_object(rationale_tags: List[str]) -> Dict[str, List[str]]:
    """
    Build structured explanation object from rationale tags.
    
    This is the main entry point for Phase 3 explainability.
    
    Args:
        rationale_tags: Raw rationale tags from Phase 2 engine
        
    Returns:
        Structured explanation with drivers, risks, notes
    """
    return categorize_rationale(rationale_tags)

