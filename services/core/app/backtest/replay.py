"""
Replay runner for backtesting Phase 2 signals.

Reads historical bars from SQLite and generates signals candle-by-candle.
"""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any

from ..signals.engine import generate_signal
from ..storage.sqlite import SQLiteStore


@dataclass
class ReplayEvent:
    """Single replay event (one signal generation)."""
    ts: int
    symbol: str
    horizons: List[str]
    
    # Signal output
    state: str
    confidence: float
    
    # Trade plan
    entry_price: Optional[float]
    invalidation_price: float
    valid_until_ts: int
    size_suggestion_pct: float
    
    # Consensus
    consensus_direction: float
    agreement_score: float
    
    # Optional explanation (only if enabled)
    explanation_summary: Optional[dict] = None
    
    # Metadata
    as_of_ts: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return asdict(self)


class ReplayRunner:
    """
    Replay historical data and generate signals.
    
    This does NOT change Phase 2 logic - it just calls the engine
    repeatedly with different time windows.
    """
    
    def __init__(
        self,
        store: SQLiteStore,
        symbol: str,
        horizons: List[str],
        start_ts: int,
        end_ts: int,
        bar_limit: int = 100,
        include_explanation: bool = False,
    ):
        self.store = store
        self.symbol = symbol
        self.horizons = horizons
        self.start_ts = start_ts
        self.end_ts = end_ts
        self.bar_limit = bar_limit
        self.include_explanation = include_explanation
    
    async def run(self, progress: bool = True) -> List[ReplayEvent]:
        """
        Run replay and generate signals.
        
        Args:
            progress: Print progress messages
            
        Returns:
            List of ReplayEvent objects
        """
        # Fetch all 1m bars for the period (we need 1m for stepping)
        if progress:
            print(f"Loading 1m bars for {self.symbol} from {datetime.fromtimestamp(self.start_ts)} to {datetime.fromtimestamp(self.end_ts)}...")
        
        bars_1m = await self._fetch_bars_range(self.symbol, "1m", self.start_ts, self.end_ts)
        
        if not bars_1m:
            if progress:
                print("No bars found for replay period")
            return []
        
        if progress:
            print(f"Loaded {len(bars_1m)} 1m bars")
            print(f"Replaying signals...")
        
        events = []
        
        # Step through each 1m bar
        for i, bar in enumerate(bars_1m):
            bar_ts = bar["ts"]
            
            # Skip if before start
            if bar_ts < self.start_ts:
                continue
            
            # Stop if after end
            if bar_ts > self.end_ts:
                break
            
            # Generate signal at this timestamp
            try:
                event = await self._generate_signal_at(bar_ts)
                if event:
                    events.append(event)
                
                # Progress every 1000 bars
                if progress and (i + 1) % 1000 == 0:
                    print(f"  Processed {i + 1}/{len(bars_1m)} bars, {len(events)} signals generated")
            
            except Exception as e:
                if progress:
                    print(f"  Warning: Failed to generate signal at ts={bar_ts}: {e}")
                continue
        
        if progress:
            print(f"✓ Replay complete: {len(events)} signals generated")
        
        return events
    
    async def _generate_signal_at(self, ts: int) -> Optional[ReplayEvent]:
        """Generate signal at specific timestamp."""
        # Generate signal using Phase 2 engine
        # Note: This calls the SAME engine as /v1/signal endpoint
        response = await generate_signal(
            store=self.store,
            symbol=self.symbol,
            horizons=self.horizons,
            bar_limit=self.bar_limit,
        )
        
        # Extract key fields
        trade_plan = response.trade_plan
        consensus = response.consensus
        
        # Build explanation summary if requested
        explanation_summary = None
        if self.include_explanation and hasattr(response, 'explanation'):
            explanation_summary = {
                "drivers_count": len(response.explanation.get("drivers", [])),
                "risks_count": len(response.explanation.get("risks", [])),
                "has_conflict": any("conflict" in r.lower() for r in response.explanation.get("risks", [])),
            }
        
        # Create replay event
        event = ReplayEvent(
            ts=ts,
            symbol=self.symbol,
            horizons=self.horizons,
            state=response.state,
            confidence=response.confidence,
            entry_price=trade_plan.get("entry_price"),
            invalidation_price=trade_plan.get("invalidation_price"),
            valid_until_ts=trade_plan.get("valid_until_ts"),
            size_suggestion_pct=trade_plan.get("size_suggestion_pct"),
            consensus_direction=consensus.get("direction"),
            agreement_score=consensus.get("agreement_score"),
            explanation_summary=explanation_summary,
            as_of_ts=response.as_of_ts,
        )
        
        return event
    
    async def _fetch_bars_range(
        self,
        symbol: str,
        interval: str,
        start_ts: int,
        end_ts: int,
    ) -> List[dict]:
        """
        Fetch bars within a time range.
        
        Note: SQLiteStore.fetch_bars doesn't support time range filtering,
        so we fetch a large limit and filter client-side.
        """
        # Fetch large limit and filter
        # This is not optimal but works for backtesting
        bars = await self.store.fetch_bars(symbol, interval, limit=100000)
        
        # Filter by time range
        filtered = [b for b in bars if start_ts <= b["ts"] <= end_ts]
        
        return filtered
    
    def save_to_jsonl(self, events: List[ReplayEvent], output_path: Path):
        """Save events to JSONL file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            for event in events:
                json.dump(event.to_dict(), f)
                f.write('\n')
    
    def save_summary_json(self, events: List[ReplayEvent], output_path: Path):
        """Save summary statistics to JSON."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not events:
            summary = {"error": "No events"}
        else:
            # Compute summary stats
            states = [e.state for e in events]
            confidences = [e.confidence for e in events]
            
            summary = {
                "total_signals": len(events),
                "start_ts": events[0].ts,
                "end_ts": events[-1].ts,
                "start_dt": datetime.fromtimestamp(events[0].ts).isoformat(),
                "end_dt": datetime.fromtimestamp(events[-1].ts).isoformat(),
                "symbol": events[0].symbol,
                "horizons": events[0].horizons,
                "states": {
                    "STRONG_BUY": states.count("STRONG_BUY"),
                    "BUY": states.count("BUY"),
                    "NEUTRAL": states.count("NEUTRAL"),
                    "SELL": states.count("SELL"),
                    "STRONG_SELL": states.count("STRONG_SELL"),
                },
                "confidence": {
                    "mean": sum(confidences) / len(confidences),
                    "min": min(confidences),
                    "max": max(confidences),
                },
            }
        
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)

