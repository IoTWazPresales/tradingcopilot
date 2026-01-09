"""
Integration test for evaluation using a tiny replay file.

This tests the complete workflow: JSONL → evaluate → summary/CSV
"""

import pytest
import tempfile
import os
import json
from pathlib import Path

from app.backtest.evaluate import OutcomeEvaluator


class MockStore:
    """Mock store with pre-configured bar series."""
    
    def __init__(self, bar_data):
        """bar_data: dict[symbol][interval] -> list of bars."""
        self.bar_data = bar_data
    
    async def fetch_bars(self, symbol, interval, limit):
        """Return bars from mock data."""
        return self.bar_data.get(symbol, {}).get(interval, [])


@pytest.mark.asyncio
async def test_evaluate_integration_small_replay():
    """End-to-end evaluation test with 3 signal events."""
    
    # ========== Setup: Create synthetic price data ==========
    # Timeline:
    # t=1000: BUY signal generated at 100
    # t=1000-1180: price moves 100 → 98 (stop hit at t=1120)
    # t=2000: SELL signal generated at 95
    # t=2000-2180: price moves 95 → 93 (target hit at t=2120)
    # t=3000: BUY signal generated at 90
    # t=3000-3180: price oscillates 90-91, never hits stop/target (expires)
    
    bars_1m = [
        # First BUY signal bars (stop hit)
        {"ts": 1000, "open": 100, "high": 100.5, "low": 99.5, "close": 100},
        {"ts": 1060, "open": 100, "high": 100, "low": 99, "close": 99.5},
        {"ts": 1120, "open": 99.5, "high": 99.5, "low": 98, "close": 98.5},  # Stop hit
        {"ts": 1180, "open": 98.5, "high": 99, "low": 98, "close": 98.8},
        
        # Second SELL signal bars (target hit)
        {"ts": 2000, "open": 95, "high": 95.5, "low": 94.5, "close": 95},
        {"ts": 2060, "open": 95, "high": 95, "low": 94, "close": 94.5},
        {"ts": 2120, "open": 94.5, "high": 94.5, "low": 93, "close": 93.5},  # Target hit
        {"ts": 2180, "open": 93.5, "high": 94, "low": 93, "close": 93.8},
        
        # Third BUY signal bars (expired - never hits stop or target)
        {"ts": 3000, "open": 90, "high": 91, "low": 89.5, "close": 90.5},
        {"ts": 3060, "open": 90.5, "high": 91, "low": 90, "close": 90.8},
        {"ts": 3120, "open": 90.8, "high": 91, "low": 90.5, "close": 90.7},
        {"ts": 3180, "open": 90.7, "high": 91, "low": 90.2, "close": 90.5},
    ]
    
    store = MockStore({"BTCUSDT": {"1m": bars_1m}})
    
    # ========== Setup: Create temp replay JSONL file ==========
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        replay_path = f.name
        
        # Event 1: BUY at 100, stop=98, target=102, valid until t=2000
        f.write(json.dumps({
            "ts": 1000,
            "symbol": "BTCUSDT",
            "horizons": ["1m", "5m"],
            "state": "BUY",
            "confidence": 0.75,
            "entry_price": 100.0,
            "invalidation_price": 98.0,
            "valid_until_ts": 2000,
            "size_suggestion_pct": 1.0,
            "consensus_direction": 0.5,
            "agreement_score": 0.85,
        }) + "\n")
        
        # Event 2: SELL at 95, stop=97, target=93, valid until t=3000
        f.write(json.dumps({
            "ts": 2000,
            "symbol": "BTCUSDT",
            "horizons": ["1m", "5m"],
            "state": "SELL",
            "confidence": 0.80,
            "entry_price": 95.0,
            "invalidation_price": 97.0,
            "valid_until_ts": 3000,
            "size_suggestion_pct": 1.0,
            "consensus_direction": -0.6,
            "agreement_score": 0.90,
        }) + "\n")
        
        # Event 3: BUY at 90, stop=88, target=92, valid until t=3200 (will expire)
        f.write(json.dumps({
            "ts": 3000,
            "symbol": "BTCUSDT",
            "horizons": ["1m", "5m"],
            "state": "BUY",
            "confidence": 0.60,
            "entry_price": 90.0,
            "invalidation_price": 88.0,
            "valid_until_ts": 3200,
            "size_suggestion_pct": 0.75,
            "consensus_direction": 0.3,
            "agreement_score": 0.70,
        }) + "\n")
    
    try:
        # ========== Run evaluation ==========
        evaluator = OutcomeEvaluator(store)
        
        # Read replay events
        events = []
        with open(replay_path, 'r') as f:
            for line in f:
                events.append(json.loads(line))
        
        # Evaluate each event
        outcomes = []
        for event in events:
            outcome = await evaluator._evaluate_single(event)
            if outcome:
                outcomes.append(outcome)
        
        # Compute metrics
        summary = evaluator.compute_metrics(outcomes)
        
        # ========== Assertions ==========
        assert len(outcomes) == 3, "Should have 3 trade outcomes"
        
        # Total counts
        assert summary["total_trades"] == 3
        assert summary["wins"] == 1, "Event 2 (SELL) should win"
        assert summary["losses"] == 1, "Event 1 (BUY) should lose"
        assert summary["expired"] == 1, "Event 3 (BUY) should expire"
        
        # Rates (use approximate comparison for floating point)
        assert abs(summary["win_rate"] - 1/3) < 0.001
        assert abs(summary["loss_rate"] - 1/3) < 0.001
        assert abs(summary["expiry_rate"] - 1/3) < 0.001
        
        # Expectancy: (+1 -1 +0) / 3 = 0.0
        assert abs(summary["expectancy"]) < 0.001
        
        # Check individual outcomes
        outcomes_sorted = sorted(outcomes, key=lambda x: x.signal_ts)
        
        # Event 1: BUY loss
        assert outcomes_sorted[0].outcome == "loss"
        assert outcomes_sorted[0].R == -1.0
        assert outcomes_sorted[0].exit_ts == 1120
        
        # Event 2: SELL win
        assert outcomes_sorted[1].outcome == "win"
        assert outcomes_sorted[1].R == 1.0
        assert outcomes_sorted[1].exit_ts == 2120
        
        # Event 3: BUY expired
        assert outcomes_sorted[2].outcome == "expired"
        assert outcomes_sorted[2].R == 0.0
        assert outcomes_sorted[2].exit_ts is None
        
        # Check metrics by state
        assert "by_state" in summary
        assert summary["by_state"]["BUY"]["total"] == 2
        assert summary["by_state"]["BUY"]["losses"] == 1
        assert summary["by_state"]["BUY"]["expired"] == 1
        assert summary["by_state"]["SELL"]["total"] == 1
        assert summary["by_state"]["SELL"]["wins"] == 1
        
    finally:
        # Cleanup temp file
        os.remove(replay_path)


@pytest.mark.asyncio
async def test_evaluate_integration_write_outputs():
    """Test that evaluation writes summary JSON and trades CSV correctly."""
    
    # Setup: Simple 1-trade scenario
    bars_1m = [
        {"ts": 1000, "open": 100, "high": 102, "low": 99, "close": 101},  # Target hit
    ]
    
    store = MockStore({"BTCUSDT": {"1m": bars_1m}})
    
    # Create temp directory for outputs
    with tempfile.TemporaryDirectory() as tmpdir:
        replay_path = Path(tmpdir) / "replay.jsonl"
        
        # Write replay file
        with open(replay_path, 'w') as f:
            f.write(json.dumps({
                "ts": 1000,
                "symbol": "BTCUSDT",
                "horizons": ["1m"],
                "state": "BUY",
                "confidence": 0.75,
                "entry_price": 100.0,
                "invalidation_price": 98.0,
                "valid_until_ts": 2000,
                "size_suggestion_pct": 1.0,
                "consensus_direction": 0.5,
                "agreement_score": 0.85,
            }) + "\n")
        
        # Run evaluation
        evaluator = OutcomeEvaluator(store)
        
        events = []
        with open(replay_path, 'r') as f:
            for line in f:
                events.append(json.loads(line))
        
        outcomes = []
        for event in events:
            outcome = await evaluator._evaluate_single(event)
            if outcome:
                outcomes.append(outcome)
        
        summary = evaluator.compute_metrics(outcomes)
        
        # Write outputs
        output_prefix = Path(tmpdir) / "test_backtest"
        summary_path = Path(str(output_prefix) + "_summary.json")
        trades_path = Path(str(output_prefix) + "_trades.csv")
        
        # Write summary
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Write trades CSV
        evaluator.write_trades_csv(outcomes, trades_path)
        
        # Verify files exist
        assert summary_path.exists(), "Summary JSON should be written"
        assert trades_path.exists(), "Trades CSV should be written"
        
        # Verify summary content
        with open(summary_path, 'r') as f:
            loaded_summary = json.load(f)
            assert loaded_summary["total_trades"] == 1
            assert loaded_summary["wins"] == 1
        
        # Verify CSV content
        with open(trades_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 2, "Header + 1 trade"
            assert "signal_ts" in lines[0]
            assert "1000" in lines[1]
            assert "win" in lines[1]

