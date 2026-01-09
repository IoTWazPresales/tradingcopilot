"""
Outcome evaluation for replay signals.

Evaluates signals against subsequent price action to determine:
- Stop hit (loss)
- Target hit (win)
- Expired (neither hit within validity window)
"""

import json
import csv
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional, Any

from ..storage.sqlite import SQLiteStore


@dataclass
class TradeOutcome:
    """Outcome of a single signal/trade."""
    # Signal info
    signal_ts: int
    symbol: str
    state: str
    confidence: float
    
    # Trade plan
    entry_price: float
    invalidation_price: float
    valid_until_ts: int
    size_suggestion_pct: float
    
    # Outcome
    outcome: str  # "win", "loss", "expired"
    R: float  # Risk-reward multiple (-1 for loss, +1 for win, 0 for expired)
    exit_ts: Optional[int] = None
    exit_price: Optional[float] = None
    
    # Advanced metrics
    MAE: Optional[float] = None  # Maximum Adverse Excursion
    MFE: Optional[float] = None  # Maximum Favorable Excursion
    
    # Context
    consensus_direction: float = 0.0
    agreement_score: float = 0.0
    has_conflict: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dict."""
        return asdict(self)


class OutcomeEvaluator:
    """
    Evaluate replay signals against subsequent price action.
    
    This is deterministic and does NOT use Phase 2 logic.
    It only evaluates outcomes based on price movement.
    """
    
    def __init__(self, store: SQLiteStore):
        self.store = store
    
    async def evaluate_signals(
        self,
        replay_events: List[dict],
        progress: bool = True,
    ) -> List[TradeOutcome]:
        """
        Evaluate list of replay events.
        
        Args:
            replay_events: List of replay event dicts (from JSONL)
            progress: Print progress
            
        Returns:
            List of TradeOutcome objects
        """
        outcomes = []
        
        for i, event in enumerate(replay_events):
            # Skip NEUTRAL signals (no entry)
            if event["state"] == "NEUTRAL" or event["entry_price"] is None:
                continue
            
            try:
                outcome = await self._evaluate_single(event)
                if outcome:
                    outcomes.append(outcome)
                
                if progress and (i + 1) % 100 == 0:
                    print(f"  Evaluated {i + 1}/{len(replay_events)} events")
            
            except Exception as e:
                if progress:
                    print(f"  Warning: Failed to evaluate event at ts={event['ts']}: {e}")
                continue
        
        if progress:
            print(f"✓ Evaluated {len(outcomes)} trades")
        
        return outcomes
    
    async def _evaluate_single(self, event: dict) -> Optional[TradeOutcome]:
        """Evaluate single event."""
        symbol = event["symbol"]
        entry_price = event["entry_price"]
        invalidation_price = event["invalidation_price"]
        valid_until_ts = event["valid_until_ts"]
        signal_ts = event["ts"]
        state = event["state"]
        
        # Determine direction
        is_long = state in ["BUY", "STRONG_BUY"]
        is_short = state in ["SELL", "STRONG_SELL"]
        
        if not (is_long or is_short):
            return None
        
        # Calculate R (risk distance)
        risk_distance = abs(entry_price - invalidation_price)
        if risk_distance == 0:
            return None
        
        # Target is 1R away
        if is_long:
            target_price = entry_price + risk_distance
            stop_price = invalidation_price
        else:
            target_price = entry_price - risk_distance
            stop_price = invalidation_price
        
        # Fetch 1m bars from signal to valid_until
        bars = await self._fetch_bars_range(
            symbol=symbol,
            interval="1m",
            start_ts=signal_ts,
            end_ts=valid_until_ts,
        )
        
        if not bars:
            # No bars available - mark as expired
            return TradeOutcome(
                signal_ts=signal_ts,
                symbol=symbol,
                state=state,
                confidence=event["confidence"],
                entry_price=entry_price,
                invalidation_price=invalidation_price,
                valid_until_ts=valid_until_ts,
                size_suggestion_pct=event["size_suggestion_pct"],
                outcome="expired",
                R=0.0,
                consensus_direction=event.get("consensus_direction", 0.0),
                agreement_score=event.get("agreement_score", 0.0),
                has_conflict=event.get("explanation_summary", {}).get("has_conflict", False) if event.get("explanation_summary") else False,
            )
        
        # Check each bar for stop/target hit
        MAE = 0.0  # Maximum adverse excursion
        MFE = 0.0  # Maximum favorable excursion
        
        for bar in bars:
            high = bar["high"]
            low = bar["low"]
            ts = bar["ts"]
            
            if is_long:
                # Long trade
                # Check stop hit (low <= stop_price)
                if low <= stop_price:
                    return TradeOutcome(
                        signal_ts=signal_ts,
                        symbol=symbol,
                        state=state,
                        confidence=event["confidence"],
                        entry_price=entry_price,
                        invalidation_price=invalidation_price,
                        valid_until_ts=valid_until_ts,
                        size_suggestion_pct=event["size_suggestion_pct"],
                        outcome="loss",
                        R=-1.0,
                        exit_ts=ts,
                        exit_price=stop_price,
                        MAE=-risk_distance,
                        MFE=MFE,
                        consensus_direction=event.get("consensus_direction", 0.0),
                        agreement_score=event.get("agreement_score", 0.0),
                        has_conflict=event.get("explanation_summary", {}).get("has_conflict", False) if event.get("explanation_summary") else False,
                    )
                
                # Check target hit (high >= target_price)
                if high >= target_price:
                    return TradeOutcome(
                        signal_ts=signal_ts,
                        symbol=symbol,
                        state=state,
                        confidence=event["confidence"],
                        entry_price=entry_price,
                        invalidation_price=invalidation_price,
                        valid_until_ts=valid_until_ts,
                        size_suggestion_pct=event["size_suggestion_pct"],
                        outcome="win",
                        R=+1.0,
                        exit_ts=ts,
                        exit_price=target_price,
                        MAE=MAE,
                        MFE=risk_distance,
                        consensus_direction=event.get("consensus_direction", 0.0),
                        agreement_score=event.get("agreement_score", 0.0),
                        has_conflict=event.get("explanation_summary", {}).get("has_conflict", False) if event.get("explanation_summary") else False,
                    )
                
                # Track MAE/MFE
                MAE = min(MAE, low - entry_price)
                MFE = max(MFE, high - entry_price)
            
            else:
                # Short trade
                # Check stop hit (high >= stop_price)
                if high >= stop_price:
                    return TradeOutcome(
                        signal_ts=signal_ts,
                        symbol=symbol,
                        state=state,
                        confidence=event["confidence"],
                        entry_price=entry_price,
                        invalidation_price=invalidation_price,
                        valid_until_ts=valid_until_ts,
                        size_suggestion_pct=event["size_suggestion_pct"],
                        outcome="loss",
                        R=-1.0,
                        exit_ts=ts,
                        exit_price=stop_price,
                        MAE=-risk_distance,
                        MFE=MFE,
                        consensus_direction=event.get("consensus_direction", 0.0),
                        agreement_score=event.get("agreement_score", 0.0),
                        has_conflict=event.get("explanation_summary", {}).get("has_conflict", False) if event.get("explanation_summary") else False,
                    )
                
                # Check target hit (low <= target_price)
                if low <= target_price:
                    return TradeOutcome(
                        signal_ts=signal_ts,
                        symbol=symbol,
                        state=state,
                        confidence=event["confidence"],
                        entry_price=entry_price,
                        invalidation_price=invalidation_price,
                        valid_until_ts=valid_until_ts,
                        size_suggestion_pct=event["size_suggestion_pct"],
                        outcome="win",
                        R=+1.0,
                        exit_ts=ts,
                        exit_price=target_price,
                        MAE=MAE,
                        MFE=risk_distance,
                        consensus_direction=event.get("consensus_direction", 0.0),
                        agreement_score=event.get("agreement_score", 0.0),
                        has_conflict=event.get("explanation_summary", {}).get("has_conflict", False) if event.get("explanation_summary") else False,
                    )
                
                # Track MAE/MFE
                MAE = min(MAE, entry_price - high)
                MFE = max(MFE, entry_price - low)
        
        # Neither stop nor target hit - expired
        return TradeOutcome(
            signal_ts=signal_ts,
            symbol=symbol,
            state=state,
            confidence=event["confidence"],
            entry_price=entry_price,
            invalidation_price=invalidation_price,
            valid_until_ts=valid_until_ts,
            size_suggestion_pct=event["size_suggestion_pct"],
            outcome="expired",
            R=0.0,
            MAE=MAE,
            MFE=MFE,
            consensus_direction=event.get("consensus_direction", 0.0),
            agreement_score=event.get("agreement_score", 0.0),
            has_conflict=event.get("explanation_summary", {}).get("has_conflict", False) if event.get("explanation_summary") else False,
        )
    
    async def _fetch_bars_range(
        self,
        symbol: str,
        interval: str,
        start_ts: int,
        end_ts: int,
    ) -> List[dict]:
        """Fetch bars within time range."""
        bars = await self.store.fetch_bars(symbol, interval, limit=100000)
        filtered = [b for b in bars if start_ts <= b["ts"] <= end_ts]
        return filtered
    
    def compute_metrics(self, outcomes: List[TradeOutcome]) -> Dict[str, Any]:
        """Compute summary metrics from outcomes."""
        if not outcomes:
            return {"error": "No outcomes"}
        
        wins = [o for o in outcomes if o.outcome == "win"]
        losses = [o for o in outcomes if o.outcome == "loss"]
        expired = [o for o in outcomes if o.outcome == "expired"]
        
        total = len(outcomes)
        win_count = len(wins)
        loss_count = len(losses)
        expired_count = len(expired)
        
        win_rate = win_count / total if total > 0 else 0.0
        loss_rate = loss_count / total if total > 0 else 0.0
        expiry_rate = expired_count / total if total > 0 else 0.0
        
        # Expectancy
        total_R = sum(o.R for o in outcomes)
        expectancy = total_R / total if total > 0 else 0.0
        
        # By state
        states = {}
        for state in ["STRONG_BUY", "BUY", "SELL", "STRONG_SELL"]:
            state_outcomes = [o for o in outcomes if o.state == state]
            if state_outcomes:
                state_wins = [o for o in state_outcomes if o.outcome == "win"]
                state_losses = [o for o in state_outcomes if o.outcome == "loss"]
                state_expired = [o for o in state_outcomes if o.outcome == "expired"]
                states[state] = {
                    "total": len(state_outcomes),
                    "wins": len(state_wins),
                    "losses": len(state_losses),
                    "expired": len(state_expired),
                    "win_rate": len(state_wins) / len(state_outcomes),
                    "expectancy": sum(o.R for o in state_outcomes) / len(state_outcomes),
                }
        
        # By confidence bands
        bands = {
            "low (0-0.3)": [o for o in outcomes if o.confidence < 0.3],
            "medium (0.3-0.6)": [o for o in outcomes if 0.3 <= o.confidence < 0.6],
            "high (0.6-1.0)": [o for o in outcomes if o.confidence >= 0.6],
        }
        
        confidence_metrics = {}
        for band_name, band_outcomes in bands.items():
            if band_outcomes:
                band_wins = [o for o in band_outcomes if o.outcome == "win"]
                confidence_metrics[band_name] = {
                    "total": len(band_outcomes),
                    "wins": len(band_wins),
                    "win_rate": len(band_wins) / len(band_outcomes),
                    "expectancy": sum(o.R for o in band_outcomes) / len(band_outcomes),
                }
        
        # Conflict vs non-conflict
        conflict_outcomes = [o for o in outcomes if o.has_conflict]
        non_conflict_outcomes = [o for o in outcomes if not o.has_conflict]
        
        conflict_metrics = {}
        if conflict_outcomes:
            conflict_wins = [o for o in conflict_outcomes if o.outcome == "win"]
            conflict_metrics["with_conflict"] = {
                "total": len(conflict_outcomes),
                "wins": len(conflict_wins),
                "win_rate": len(conflict_wins) / len(conflict_outcomes),
                "expectancy": sum(o.R for o in conflict_outcomes) / len(conflict_outcomes),
            }
        
        if non_conflict_outcomes:
            non_conflict_wins = [o for o in non_conflict_outcomes if o.outcome == "win"]
            conflict_metrics["without_conflict"] = {
                "total": len(non_conflict_outcomes),
                "wins": len(non_conflict_wins),
                "win_rate": len(non_conflict_wins) / len(non_conflict_outcomes),
                "expectancy": sum(o.R for o in non_conflict_outcomes) / len(non_conflict_outcomes),
            }
        
        return {
            "total_trades": total,
            "wins": win_count,
            "losses": loss_count,
            "expired": expired_count,
            "win_rate": round(win_rate, 4),
            "loss_rate": round(loss_rate, 4),
            "expiry_rate": round(expiry_rate, 4),
            "expectancy": round(expectancy, 4),
            "by_state": states,
            "by_confidence_band": confidence_metrics,
            "by_conflict": conflict_metrics,
        }
    
    def save_summary_json(self, metrics: Dict[str, Any], output_path: Path):
        """Save metrics to JSON."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=2)
    
    def save_trades_csv(self, outcomes: List[TradeOutcome], output_path: Path):
        """Save outcomes to CSV for Excel."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='') as f:
            if not outcomes:
                return
            
            fieldnames = list(outcomes[0].to_dict().keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for outcome in outcomes:
                writer.writerow(outcome.to_dict())
    
    def write_trades_csv(self, outcomes: List[TradeOutcome], output_path: Path):
        """Alias for save_trades_csv (for compatibility)."""
        self.save_trades_csv(outcomes, output_path)

