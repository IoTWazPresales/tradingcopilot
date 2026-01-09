"""Canonical types for Phase 2 signal engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SignalState(Enum):
    """Discrete signal states."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


@dataclass
class FeatureSet:
    """Features extracted from bars for a single horizon."""
    horizon: str  # e.g., "1m", "15m", "1h"
    n_bars: int
    momentum: float  # Normalized return over window
    volatility: float  # Std of returns
    trend_direction: float  # Sign of momentum (-1, 0, +1)
    stability: float  # Inverse volatility / signal-to-noise
    
    # Raw data for debugging/rationale
    last_close: float
    first_close: float
    avg_range: float  # Average (high - low)


@dataclass
class HorizonSignal:
    """Signal derived from a single horizon."""
    horizon: str
    direction_score: float  # [-1, +1]: -1=bearish, +1=bullish
    strength: float  # [0, 1]: how strong the directional bias is
    confidence: float  # [0, 1]: data quality confidence
    features: FeatureSet
    rationale: list[str] = field(default_factory=list)


@dataclass
class ConsensusSignal:
    """Multi-horizon consensus signal."""
    consensus_direction: float  # [-1, +1]: weighted avg direction
    consensus_confidence: float  # [0, 1]: combined confidence with agreement penalty
    agreement_score: float  # [0, 1]: how well horizons agree
    horizon_signals: list[HorizonSignal]
    rationale: list[str] = field(default_factory=list)


@dataclass
class TradePlan:
    """Actionable trade plan derived from signal."""
    state: SignalState
    confidence: float  # [0, 1]
    entry_price: float | None  # Suggested entry (None = "market now")
    invalidation_price: float  # Stop-loss level
    valid_until_ts: int  # Unix timestamp when plan expires
    size_suggestion_pct: float  # % of capital (e.g., 0.5, 1.0, 2.0)
    rationale: list[str]
    
    # Metadata
    symbol: str
    as_of_ts: int
    horizons_analyzed: list[str]


@dataclass
class SignalResponse:
    """Final API response for /v1/signal endpoint."""
    symbol: str
    state: str  # SignalState.value for JSON serialization
    confidence: float
    trade_plan: dict[str, Any]  # TradePlan serialized
    consensus: dict[str, Any]  # ConsensusSignal summary
    horizon_details: list[dict[str, Any]]  # HorizonSignal summaries
    as_of_ts: int
    
    # API metadata
    version: str = "2.0"
    phase: str = "Phase 2"

