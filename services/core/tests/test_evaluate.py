"""
Deterministic unit tests for outcome evaluation logic.

These tests use synthetic data to verify stop/target hit detection is correct.
"""

import pytest
from datetime import datetime

from app.backtest.evaluate import OutcomeEvaluator, TradeOutcome


class MockStore:
    """Mock store for testing."""
    
    def __init__(self, bars_data):
        self.bars_data = bars_data
    
    async def fetch_bars(self, symbol, interval, limit):
        """Return pre-configured bars."""
        return self.bars_data.get(symbol, {}).get(interval, [])


class TestEvaluateBuyCases:
    """Test BUY signal evaluation."""
    
    @pytest.mark.asyncio
    async def test_buy_stop_hit_first(self):
        """BUY: Stop hit before target → loss, R=-1."""
        # Setup: entry=100, stop=98, target=102
        # Price goes: 100 → 99 → 98 (stop hit) → never reaches 102
        bars = [
            {"ts": 1000, "open": 100, "high": 100.5, "low": 99, "close": 99.5},
            {"ts": 1060, "open": 99.5, "high": 99.5, "low": 98, "close": 98.2},  # Stop hit at low=98
            {"ts": 1120, "open": 98.2, "high": 99, "low": 98, "close": 98.5},
        ]
        
        store = MockStore({"BTCUSDT": {"1m": bars}})
        evaluator = OutcomeEvaluator(store)
        
        event = {
            "ts": 1000,
            "symbol": "BTCUSDT",
            "state": "BUY",
            "confidence": 0.75,
            "entry_price": 100.0,
            "invalidation_price": 98.0,  # Stop
            "valid_until_ts": 2000,
            "size_suggestion_pct": 1.0,
            "consensus_direction": 0.5,
            "agreement_score": 0.85,
        }
        
        outcome = await evaluator._evaluate_single(event)
        
        assert outcome is not None
        assert outcome.outcome == "loss"
        assert outcome.R == -1.0
        assert outcome.exit_ts == 1060  # Stopped at second bar
        assert outcome.exit_price == 98.0
        assert outcome.MAE == -2.0  # Entry 100 - stop 98 = -2
    
    @pytest.mark.asyncio
    async def test_buy_target_hit_first(self):
        """BUY: Target hit before stop → win, R=+1."""
        # Setup: entry=100, stop=98, target=102
        # Price goes: 100 → 101 → 102 (target hit) → never touches 98
        bars = [
            {"ts": 1000, "open": 100, "high": 101, "low": 99.5, "close": 100.5},
            {"ts": 1060, "open": 100.5, "high": 102, "low": 100, "close": 101.5},  # Target hit at high=102
            {"ts": 1120, "open": 101.5, "high": 102, "low": 101, "close": 101.8},
        ]
        
        store = MockStore({"BTCUSDT": {"1m": bars}})
        evaluator = OutcomeEvaluator(store)
        
        event = {
            "ts": 1000,
            "symbol": "BTCUSDT",
            "state": "BUY",
            "confidence": 0.75,
            "entry_price": 100.0,
            "invalidation_price": 98.0,
            "valid_until_ts": 2000,
            "size_suggestion_pct": 1.0,
            "consensus_direction": 0.5,
            "agreement_score": 0.85,
        }
        
        outcome = await evaluator._evaluate_single(event)
        
        assert outcome is not None
        assert outcome.outcome == "win"
        assert outcome.R == +1.0
        assert outcome.exit_ts == 1060  # Won at second bar
        assert outcome.exit_price == 102.0
        assert outcome.MFE == 2.0  # Target 102 - entry 100 = +2
    
    @pytest.mark.asyncio
    async def test_buy_expired(self):
        """BUY: Neither stop nor target hit → expired, R=0."""
        # Setup: entry=100, stop=98, target=102
        # Price oscillates between 99-101, never touching 98 or 102
        bars = [
            {"ts": 1000, "open": 100, "high": 101, "low": 99, "close": 100.5},
            {"ts": 1060, "open": 100.5, "high": 101, "low": 99.5, "close": 100},
            {"ts": 1120, "open": 100, "high": 100.8, "low": 99.2, "close": 100.2},
        ]
        
        store = MockStore({"BTCUSDT": {"1m": bars}})
        evaluator = OutcomeEvaluator(store)
        
        event = {
            "ts": 1000,
            "symbol": "BTCUSDT",
            "state": "BUY",
            "confidence": 0.75,
            "entry_price": 100.0,
            "invalidation_price": 98.0,
            "valid_until_ts": 1200,  # Expires after 3 bars
            "size_suggestion_pct": 1.0,
            "consensus_direction": 0.5,
            "agreement_score": 0.85,
        }
        
        outcome = await evaluator._evaluate_single(event)
        
        assert outcome is not None
        assert outcome.outcome == "expired"
        assert outcome.R == 0.0
        assert outcome.exit_ts is None
        assert outcome.exit_price is None
        # MAE/MFE should track the worst/best moves seen
        assert outcome.MAE is not None
        assert outcome.MFE is not None


class TestEvaluateSellCases:
    """Test SELL signal evaluation."""
    
    @pytest.mark.asyncio
    async def test_sell_stop_hit_first(self):
        """SELL: Stop hit before target → loss, R=-1."""
        # Setup: entry=100, stop=102, target=98
        # Price goes: 100 → 101 → 102 (stop hit) → never reaches 98
        bars = [
            {"ts": 1000, "open": 100, "high": 101, "low": 99.5, "close": 100.5},
            {"ts": 1060, "open": 100.5, "high": 102, "low": 100, "close": 101.5},  # Stop hit at high=102
            {"ts": 1120, "open": 101.5, "high": 101.8, "low": 101, "close": 101.2},
        ]
        
        store = MockStore({"BTCUSDT": {"1m": bars}})
        evaluator = OutcomeEvaluator(store)
        
        event = {
            "ts": 1000,
            "symbol": "BTCUSDT",
            "state": "SELL",
            "confidence": 0.75,
            "entry_price": 100.0,
            "invalidation_price": 102.0,  # Stop (above entry for short)
            "valid_until_ts": 2000,
            "size_suggestion_pct": 1.0,
            "consensus_direction": -0.5,
            "agreement_score": 0.85,
        }
        
        outcome = await evaluator._evaluate_single(event)
        
        assert outcome is not None
        assert outcome.outcome == "loss"
        assert outcome.R == -1.0
        assert outcome.exit_ts == 1060
        assert outcome.exit_price == 102.0
        assert outcome.MAE == -2.0  # Risk distance
    
    @pytest.mark.asyncio
    async def test_sell_target_hit_first(self):
        """SELL: Target hit before stop → win, R=+1."""
        # Setup: entry=100, stop=102, target=98
        # Price goes: 100 → 99 → 98 (target hit) → never touches 102
        bars = [
            {"ts": 1000, "open": 100, "high": 100.5, "low": 99, "close": 99.5},
            {"ts": 1060, "open": 99.5, "high": 99.5, "low": 98, "close": 98.5},  # Target hit at low=98
            {"ts": 1120, "open": 98.5, "high": 99, "low": 98.2, "close": 98.8},
        ]
        
        store = MockStore({"BTCUSDT": {"1m": bars}})
        evaluator = OutcomeEvaluator(store)
        
        event = {
            "ts": 1000,
            "symbol": "BTCUSDT",
            "state": "SELL",
            "confidence": 0.75,
            "entry_price": 100.0,
            "invalidation_price": 102.0,
            "valid_until_ts": 2000,
            "size_suggestion_pct": 1.0,
            "consensus_direction": -0.5,
            "agreement_score": 0.85,
        }
        
        outcome = await evaluator._evaluate_single(event)
        
        assert outcome is not None
        assert outcome.outcome == "win"
        assert outcome.R == +1.0
        assert outcome.exit_ts == 1060
        assert outcome.exit_price == 98.0
        assert outcome.MFE == 2.0  # Entry 100 - target 98 = +2 profit for short
    
    @pytest.mark.asyncio
    async def test_sell_expired(self):
        """SELL: Neither stop nor target hit → expired, R=0."""
        # Setup: entry=100, stop=102, target=98
        # Price oscillates between 99-101
        bars = [
            {"ts": 1000, "open": 100, "high": 101, "low": 99, "close": 100.5},
            {"ts": 1060, "open": 100.5, "high": 101, "low": 99.5, "close": 100},
            {"ts": 1120, "open": 100, "high": 100.8, "low": 99.2, "close": 100.2},
        ]
        
        store = MockStore({"BTCUSDT": {"1m": bars}})
        evaluator = OutcomeEvaluator(store)
        
        event = {
            "ts": 1000,
            "symbol": "BTCUSDT",
            "state": "SELL",
            "confidence": 0.75,
            "entry_price": 100.0,
            "invalidation_price": 102.0,
            "valid_until_ts": 1200,
            "size_suggestion_pct": 1.0,
            "consensus_direction": -0.5,
            "agreement_score": 0.85,
        }
        
        outcome = await evaluator._evaluate_single(event)
        
        assert outcome is not None
        assert outcome.outcome == "expired"
        assert outcome.R == 0.0


class TestEvaluateEdgeCases:
    """Test edge cases and MAE/MFE tracking."""
    
    @pytest.mark.asyncio
    async def test_mae_mfe_tracking_buy(self):
        """Verify MAE/MFE are computed correctly for BUY."""
        # Entry=100, stop=98, target=102
        # Price moves: 100 → 99.5 (MAE=-0.5) → 101.5 (MFE=+1.5) → 102 (win)
        bars = [
            {"ts": 1000, "open": 100, "high": 100.2, "low": 99.5, "close": 100},  # MAE = -0.5
            {"ts": 1060, "open": 100, "high": 101.5, "low": 99.8, "close": 101},  # MFE = +1.5
            {"ts": 1120, "open": 101, "high": 102, "low": 100.8, "close": 101.8},  # Target hit
        ]
        
        store = MockStore({"BTCUSDT": {"1m": bars}})
        evaluator = OutcomeEvaluator(store)
        
        event = {
            "ts": 1000,
            "symbol": "BTCUSDT",
            "state": "BUY",
            "confidence": 0.75,
            "entry_price": 100.0,
            "invalidation_price": 98.0,
            "valid_until_ts": 2000,
            "size_suggestion_pct": 1.0,
            "consensus_direction": 0.5,
            "agreement_score": 0.85,
        }
        
        outcome = await evaluator._evaluate_single(event)
        
        assert outcome.outcome == "win"
        # MAE should be worst adverse move seen (negative for loss)
        # MFE should be risk distance (target - entry) for win
        assert outcome.MFE == 2.0  # Full 1R = 102 - 100
    
    @pytest.mark.asyncio
    async def test_stop_hit_uses_candle_extremes(self):
        """Verify stop detection uses candle low/high, not close."""
        # Entry=100, stop=98
        # Bar has low=97.5 (touches stop) but closes at 99.5
        bars = [
            {"ts": 1000, "open": 100, "high": 100, "low": 97.5, "close": 99.5},  # Low touches stop
        ]
        
        store = MockStore({"BTCUSDT": {"1m": bars}})
        evaluator = OutcomeEvaluator(store)
        
        event = {
            "ts": 1000,
            "symbol": "BTCUSDT",
            "state": "BUY",
            "confidence": 0.75,
            "entry_price": 100.0,
            "invalidation_price": 98.0,
            "valid_until_ts": 2000,
            "size_suggestion_pct": 1.0,
            "consensus_direction": 0.5,
            "agreement_score": 0.85,
        }
        
        outcome = await evaluator._evaluate_single(event)
        
        # Even though close is 99.5 (not stopped out), low=97.5 touched stop
        assert outcome.outcome == "loss"
        assert outcome.R == -1.0
    
    @pytest.mark.asyncio
    async def test_target_hit_uses_candle_extremes(self):
        """Verify target detection uses candle high, not close."""
        # Entry=100, target=102
        # Bar has high=102.5 (touches target) but closes at 100.5
        bars = [
            {"ts": 1000, "open": 100, "high": 102.5, "low": 99, "close": 100.5},  # High touches target
        ]
        
        store = MockStore({"BTCUSDT": {"1m": bars}})
        evaluator = OutcomeEvaluator(store)
        
        event = {
            "ts": 1000,
            "symbol": "BTCUSDT",
            "state": "BUY",
            "confidence": 0.75,
            "entry_price": 100.0,
            "invalidation_price": 98.0,
            "valid_until_ts": 2000,
            "size_suggestion_pct": 1.0,
            "consensus_direction": 0.5,
            "agreement_score": 0.85,
        }
        
        outcome = await evaluator._evaluate_single(event)
        
        # Even though close is 100.5, high=102.5 touched target
        assert outcome.outcome == "win"
        assert outcome.R == +1.0
    
    @pytest.mark.asyncio
    async def test_neutral_signal_skipped(self):
        """NEUTRAL signals (no entry price) should return None."""
        store = MockStore({"BTCUSDT": {"1m": []}})
        evaluator = OutcomeEvaluator(store)
        
        event = {
            "ts": 1000,
            "symbol": "BTCUSDT",
            "state": "NEUTRAL",
            "confidence": 0.5,
            "entry_price": None,  # No entry for neutral
            "invalidation_price": 100.0,
            "valid_until_ts": 2000,
            "size_suggestion_pct": 0.25,
            "consensus_direction": 0.0,
            "agreement_score": 0.5,
        }
        
        outcome = await evaluator._evaluate_single(event)
        
        assert outcome is None
    
    @pytest.mark.asyncio
    async def test_no_bars_available(self):
        """When no bars available, should mark as expired."""
        store = MockStore({"BTCUSDT": {"1m": []}})  # Empty bars
        evaluator = OutcomeEvaluator(store)
        
        event = {
            "ts": 1000,
            "symbol": "BTCUSDT",
            "state": "BUY",
            "confidence": 0.75,
            "entry_price": 100.0,
            "invalidation_price": 98.0,
            "valid_until_ts": 2000,
            "size_suggestion_pct": 1.0,
            "consensus_direction": 0.5,
            "agreement_score": 0.85,
        }
        
        outcome = await evaluator._evaluate_single(event)
        
        assert outcome is not None
        assert outcome.outcome == "expired"
        assert outcome.R == 0.0


class TestComputeMetrics:
    """Test summary metrics computation."""
    
    def test_metrics_basic(self):
        """Test basic metrics calculation."""
        outcomes = [
            TradeOutcome(
                signal_ts=1000, symbol="BTCUSDT", state="BUY", confidence=0.7,
                entry_price=100, invalidation_price=98, valid_until_ts=2000,
                size_suggestion_pct=1.0, outcome="win", R=1.0,
                consensus_direction=0.5, agreement_score=0.8, has_conflict=False,
            ),
            TradeOutcome(
                signal_ts=1100, symbol="BTCUSDT", state="BUY", confidence=0.6,
                entry_price=100, invalidation_price=98, valid_until_ts=2000,
                size_suggestion_pct=1.0, outcome="loss", R=-1.0,
                consensus_direction=0.5, agreement_score=0.8, has_conflict=False,
            ),
            TradeOutcome(
                signal_ts=1200, symbol="BTCUSDT", state="BUY", confidence=0.5,
                entry_price=100, invalidation_price=98, valid_until_ts=2000,
                size_suggestion_pct=1.0, outcome="expired", R=0.0,
                consensus_direction=0.5, agreement_score=0.8, has_conflict=False,
            ),
        ]
        
        evaluator = OutcomeEvaluator(None)
        metrics = evaluator.compute_metrics(outcomes)
        
        assert metrics["total_trades"] == 3
        assert metrics["wins"] == 1
        assert metrics["losses"] == 1
        assert metrics["expired"] == 1
        assert abs(metrics["win_rate"] - 1/3) < 0.001
        assert abs(metrics["loss_rate"] - 1/3) < 0.001
        assert abs(metrics["expiry_rate"] - 1/3) < 0.001
        assert abs(metrics["expectancy"]) < 0.001  # (+1 -1 +0) / 3 = 0
    
    def test_metrics_by_confidence_band(self):
        """Test metrics grouped by confidence bands."""
        outcomes = [
            TradeOutcome(
                signal_ts=1000, symbol="BTCUSDT", state="BUY", confidence=0.2,
                entry_price=100, invalidation_price=98, valid_until_ts=2000,
                size_suggestion_pct=1.0, outcome="loss", R=-1.0,
                consensus_direction=0.5, agreement_score=0.8, has_conflict=False,
            ),
            TradeOutcome(
                signal_ts=1100, symbol="BTCUSDT", state="BUY", confidence=0.8,
                entry_price=100, invalidation_price=98, valid_until_ts=2000,
                size_suggestion_pct=1.0, outcome="win", R=1.0,
                consensus_direction=0.5, agreement_score=0.8, has_conflict=False,
            ),
        ]
        
        evaluator = OutcomeEvaluator(None)
        metrics = evaluator.compute_metrics(outcomes)
        
        assert "by_confidence_band" in metrics
        assert "low (0-0.3)" in metrics["by_confidence_band"]
        assert "high (0.6-1.0)" in metrics["by_confidence_band"]
        
        # Low confidence trade lost
        assert metrics["by_confidence_band"]["low (0-0.3)"]["wins"] == 0
        assert metrics["by_confidence_band"]["low (0-0.3)"]["expectancy"] == -1.0
        
        # High confidence trade won
        assert metrics["by_confidence_band"]["high (0.6-1.0)"]["wins"] == 1
        assert metrics["by_confidence_band"]["high (0.6-1.0)"]["expectancy"] == 1.0

