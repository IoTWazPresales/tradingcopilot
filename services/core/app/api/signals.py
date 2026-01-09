"""Phase 2 signal API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..signals.config import DEFAULT_HORIZONS
from ..signals.engine import generate_signal
from ..storage.sqlite import SQLiteStore

# This router will be included in main app
router = APIRouter(prefix="/v1/signal", tags=["Phase 2 - Signals"])

# Global store reference (will be set by main.py)
_store: SQLiteStore | None = None


def set_store(store: SQLiteStore) -> None:
    """Set the store reference (called from main.py)."""
    global _store
    _store = store


class SignalRequest(BaseModel):
    """Request for signal generation."""
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    horizons: list[str] | None = Field(
        None,
        description="Timeframes to analyze (default: 1m,5m,15m,1h,4h,1d)",
    )
    bar_limit: int = Field(
        100,
        ge=20,
        le=500,
        description="Number of bars to fetch per horizon",
    )
    explain: bool = Field(
        False,
        description="Include confidence breakdown and structured explanation",
    )
    debug: bool = Field(
        False,
        description="Include full debug trace with intermediate calculations",
    )


@router.post("")
async def generate_trading_signal(req: SignalRequest) -> dict:
    """
    Generate trading signal with multi-horizon analysis and trade plan.
    
    Phase 2 endpoint - does not modify Phase 1 behavior.
    Phase 3 additions: Optional explainability (explain=true) and debug trace (debug=true)
    
    Returns:
    - Discrete signal state (STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL)
    - Consensus confidence [0, 1]
    - Trade plan (entry, invalidation, validity, size suggestion)
    - Multi-horizon analysis details
    - Rationale tags explaining the signal
    - [Optional] Structured explanation (drivers, risks, notes)
    - [Optional] Confidence breakdown (data quality, agreement)
    - [Optional] Debug trace (intermediate calculations)
    """
    if _store is None:
        raise HTTPException(status_code=500, detail="Store not initialized")
    
    try:
        # Phase 2: Generate signal (unchanged)
        response = await generate_signal(
            store=_store,
            symbol=req.symbol.upper(),  # Normalize symbol
            horizons=req.horizons,
            bar_limit=req.bar_limit,
        )
        
        # Base response (always included)
        result = {
            "symbol": response.symbol,
            "state": response.state,
            "confidence": response.confidence,
            "trade_plan": response.trade_plan,
            "consensus": response.consensus,
            "horizon_details": response.horizon_details,
            "as_of_ts": response.as_of_ts,
            "version": response.version,
            "phase": response.phase,
        }
        
        # Phase 3: Add explainability if requested
        if req.explain or req.debug:
            from ..signals.rationale import build_explanation_object
            from ..signals.explainability import compute_confidence_breakdown
            from ..signals.types import ConsensusSignal, HorizonSignal
            
            # Reconstruct objects from serialized data (Phase 3 only)
            # We need the original objects for explainability
            horizon_signals_objs = []
            # For now, we'll work with the serialized data
            # This is safe since we're not changing any calculations
            
            # Build explanation from trade plan rationale
            explanation = build_explanation_object(response.trade_plan.get("rationale", []))
            result["explanation"] = explanation
            
            # Add confidence breakdown
            # We'll extract this from consensus data
            result["confidence_breakdown"] = {
                "total": response.confidence,
                "data_quality": response.consensus.get("confidence", 0.0),
                "agreement": response.consensus.get("agreement_score", 0.0),
                "explanation": {
                    "total": f"Consensus confidence based on {len(response.horizon_details)} timeframes",
                    "data_quality": "Average confidence across analyzed timeframes",
                    "agreement": "Alignment between timeframe signals",
                }
            }
        
        # Phase 3: Add debug trace if requested
        if req.debug:
            from ..signals.config import DEFAULT_HORIZONS
            
            result["debug_trace"] = {
                "horizons_analyzed": [h["horizon"] for h in response.horizon_details],
                "horizons_requested": req.horizons or DEFAULT_HORIZONS,
                "horizon_details": response.horizon_details,  # Already detailed
                "consensus_calculation": {
                    "direction": response.consensus.get("direction", 0.0),
                    "confidence": response.consensus.get("confidence", 0.0),
                    "agreement_score": response.consensus.get("agreement_score", 0.0),
                },
                "rationale_tags": response.consensus.get("rationale", []),
                "note": "Debug trace shows intermediate values from Phase 2. No recalculation performed.",
            }
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating signal: {str(e)}",
        )


@router.get("/schema")
async def get_signal_schema() -> dict:
    """
    Get schema information for signal endpoint.
    
    Returns example response structure and field descriptions.
    """
    return {
        "endpoint": "/v1/signal",
        "method": "POST",
        "description": "Generate trading signal with multi-horizon analysis",
        "request_schema": {
            "symbol": "string (required) - e.g., BTCUSDT",
            "horizons": "array[string] (optional) - e.g., ['1m','15m','1h']",
            "bar_limit": "integer (optional, default=100) - bars per horizon",
        },
        "response_schema": {
            "symbol": "string",
            "state": "enum - STRONG_BUY|BUY|NEUTRAL|SELL|STRONG_SELL",
            "confidence": "float [0,1]",
            "trade_plan": {
                "entry_price": "float|null",
                "invalidation_price": "float (stop-loss)",
                "valid_until_ts": "int (unix timestamp)",
                "size_suggestion_pct": "float (% of capital)",
                "rationale": "array[string] (explanation tags)",
            },
            "consensus": {
                "direction": "float [-1,1] (bearish to bullish)",
                "confidence": "float [0,1]",
                "agreement_score": "float [0,1]",
                "rationale": "array[string]",
            },
            "horizon_details": "array[object] (per-timeframe analysis)",
        },
        "example_request": {
            "symbol": "BTCUSDT",
            "horizons": ["5m", "15m", "1h", "1d"],
            "bar_limit": 100,
        },
        "default_horizons": DEFAULT_HORIZONS,
    }

