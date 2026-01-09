"""Main signal engine orchestrating all Phase 2 components."""

from __future__ import annotations

from typing import Any

from ..storage.sqlite import SQLiteStore
from .agreement import compute_consensus, compute_horizon_signal
from .config import DEFAULT_HORIZONS
from .states import map_to_signal_state
from .trade_plan import generate_trade_plan
from .types import SignalResponse


async def generate_signal(
    store: SQLiteStore,
    symbol: str,
    horizons: list[str] | None = None,
    bar_limit: int = 100,
) -> SignalResponse:
    """
    Generate complete signal response for a symbol.
    
    This is the main entry point for Phase 2 signal generation.
    Orchestrates: feature extraction → horizon signals → consensus → state → trade plan
    
    Args:
        store: SQLiteStore for fetching bars (Phase 1 interface)
        symbol: Trading symbol (e.g., "BTCUSDT")
        horizons: List of timeframes to analyze (defaults to config)
        bar_limit: Number of bars to fetch per horizon
        
    Returns:
        SignalResponse with complete signal analysis
    """
    if horizons is None:
        horizons = DEFAULT_HORIZONS
    
    # Step 1: Fetch bars for all horizons
    horizon_bars = {}
    for horizon in horizons:
        try:
            bars = await store.fetch_bars(
                symbol=symbol,
                interval=horizon,
                limit=bar_limit,
            )
            horizon_bars[horizon] = bars
        except Exception as e:
            # Log but continue with other horizons
            print(f"Warning: Could not fetch bars for {symbol} {horizon}: {e}")
            horizon_bars[horizon] = []
    
    # Step 2: Compute signal for each horizon
    horizon_signals = []
    for horizon in horizons:
        bars = horizon_bars.get(horizon, [])
        if bars:  # Only compute if we have data
            signal = compute_horizon_signal(horizon, bars)
            horizon_signals.append(signal)
    
    # Step 3: Compute multi-horizon consensus
    consensus = compute_consensus(horizon_signals)
    
    # Step 4: Map to discrete state
    state, rationale = map_to_signal_state(consensus)
    
    # Step 5: Generate trade plan
    # Use 1m bars for invalidation calc (most granular)
    bars_1m = horizon_bars.get("1m", [])
    if not bars_1m and horizon_bars:
        # Fallback to any available bars
        bars_1m = next(iter(horizon_bars.values()))
    
    trade_plan = generate_trade_plan(
        symbol=symbol,
        state=state,
        confidence=consensus.consensus_confidence,
        consensus=consensus,
        bars_1m=bars_1m,
        rationale=rationale,
    )
    
    # Step 6: Build API response
    response = SignalResponse(
        symbol=symbol,
        state=state.value,
        confidence=consensus.consensus_confidence,
        trade_plan=_serialize_trade_plan(trade_plan),
        consensus=_serialize_consensus(consensus),
        horizon_details=[_serialize_horizon_signal(s) for s in horizon_signals],
        as_of_ts=trade_plan.as_of_ts,
    )
    
    return response


def _serialize_trade_plan(plan: Any) -> dict[str, Any]:
    """Serialize TradePlan to dict for JSON response."""
    return {
        "state": plan.state.value,
        "confidence": round(plan.confidence, 4),
        "entry_price": round(plan.entry_price, 2) if plan.entry_price else None,
        "invalidation_price": round(plan.invalidation_price, 2),
        "valid_until_ts": plan.valid_until_ts,
        "size_suggestion_pct": round(plan.size_suggestion_pct, 2),
        "rationale": plan.rationale,
        "horizons_analyzed": plan.horizons_analyzed,
    }


def _serialize_consensus(consensus: Any) -> dict[str, Any]:
    """Serialize ConsensusSignal to dict for JSON response."""
    return {
        "direction": round(consensus.consensus_direction, 4),
        "confidence": round(consensus.consensus_confidence, 4),
        "agreement_score": round(consensus.agreement_score, 4),
        "rationale": consensus.rationale,
    }


def _serialize_horizon_signal(signal: Any) -> dict[str, Any]:
    """Serialize HorizonSignal to dict for JSON response."""
    return {
        "horizon": signal.horizon,
        "direction_score": round(signal.direction_score, 4),
        "strength": round(signal.strength, 4),
        "confidence": round(signal.confidence, 4),
        "rationale": signal.rationale,
        "features": {
            "n_bars": signal.features.n_bars,
            "momentum": round(signal.features.momentum, 4),
            "volatility": round(signal.features.volatility, 6),
            "trend_direction": signal.features.trend_direction,
            "stability": round(signal.features.stability, 4),
        },
    }

