"""Unit tests for trade planning."""

import pytest

from app.signals.trade_plan import (
    compute_buy_invalidation,
    compute_sell_invalidation,
    generate_trade_plan,
    get_size_suggestion,
)
from app.signals.types import ConsensusSignal, HorizonSignal, FeatureSet, SignalState


class TestComputeBuyInvalidation:
    """Tests for compute_buy_invalidation function."""
    
    def test_uses_recent_swing_low(self):
        """Should use recent swing low as basis."""
        bars = [
            {"low": 100, "high": 102, "close": 101},
            {"low": 98, "high": 101, "close": 100},   # Swing low
            {"low": 99, "high": 103, "close": 102},
            {"low": 101, "high": 104, "close": 103},
        ]
        current = 103.0
        invalidation = compute_buy_invalidation(bars, current)
        # Should be below 98 (swing low) with 2% buffer
        assert invalidation < 98.0
        assert invalidation < current
    
    def test_below_current_price(self):
        """Invalidation must be below current price."""
        bars = [
            {"low": 100, "high": 102, "close": 101},
            {"low": 99, "high": 101, "close": 100},
        ]
        current = 101.0
        invalidation = compute_buy_invalidation(bars, current)
        assert invalidation < current
    
    def test_empty_bars_uses_buffer(self):
        """With no bars, should use current price minus buffer."""
        bars = []
        current = 100.0
        invalidation = compute_buy_invalidation(bars, current)
        assert invalidation < current
        assert invalidation > current * 0.95  # Approximately 2% buffer


class TestComputeSellInvalidation:
    """Tests for compute_sell_invalidation function."""
    
    def test_uses_recent_swing_high(self):
        """Should use recent swing high as basis."""
        bars = [
            {"low": 100, "high": 105, "close": 103},  # Swing high
            {"low": 101, "high": 104, "close": 102},
            {"low": 100, "high": 103, "close": 101},
            {"low": 99, "high": 102, "close": 100},
        ]
        current = 100.0
        invalidation = compute_sell_invalidation(bars, current)
        # Should be above 105 (swing high) with 2% buffer
        assert invalidation > 105.0
        assert invalidation > current
    
    def test_above_current_price(self):
        """Invalidation must be above current price."""
        bars = [
            {"low": 100, "high": 102, "close": 101},
            {"low": 99, "high": 101, "close": 100},
        ]
        current = 100.0
        invalidation = compute_sell_invalidation(bars, current)
        assert invalidation > current
    
    def test_empty_bars_uses_buffer(self):
        """With no bars, should use current price plus buffer."""
        bars = []
        current = 100.0
        invalidation = compute_sell_invalidation(bars, current)
        assert invalidation > current
        assert invalidation < current * 1.05  # Approximately 2% buffer


class TestGetSizeSuggestion:
    """Tests for get_size_suggestion function."""
    
    def test_low_confidence_small_size(self):
        """Low confidence should suggest small size."""
        size = get_size_suggestion(0.2)
        assert size <= 0.5, "Low confidence should be conservative"
    
    def test_high_confidence_larger_size(self):
        """High confidence should suggest larger size."""
        size = get_size_suggestion(0.9)
        assert size >= 1.5, "High confidence can be more aggressive"
    
    def test_monotonic_with_confidence(self):
        """Size should generally increase with confidence."""
        sizes = [get_size_suggestion(c) for c in [0.2, 0.4, 0.6, 0.8]]
        # Should be non-decreasing (allowing for band edges)
        assert sizes[3] >= sizes[0], "Higher confidence should not reduce size"


class TestGenerateTradePlan:
    """Tests for generate_trade_plan function."""
    
    def test_buy_plan_invalidation_below_entry(self):
        """BUY plan should have invalidation < entry."""
        bars_1m = [
            {"ts": 1000, "low": 98, "high": 102, "close": 100, "open": 99},
            {"ts": 1060, "low": 99, "high": 103, "close": 102, "open": 100},
        ]
        consensus = ConsensusSignal(
            consensus_direction=0.5,
            consensus_confidence=0.7,
            agreement_score=0.8,
            horizon_signals=[
                HorizonSignal(
                    horizon="1h",
                    direction_score=0.5,
                    strength=0.6,
                    confidence=0.7,
                    features=FeatureSet("1h", 50, 0.4, 0.02, 1.0, 0.8, 102, 100, 2.0),
                    rationale=[],
                )
            ],
            rationale=[],
        )
        
        plan = generate_trade_plan(
            symbol="BTCUSDT",
            state=SignalState.BUY,
            confidence=0.7,
            consensus=consensus,
            bars_1m=bars_1m,
            rationale=["test"],
        )
        
        assert plan.state == SignalState.BUY
        assert plan.invalidation_price < plan.entry_price, "Stop-loss must be below entry for BUY"
        assert "long_position" in plan.rationale
    
    def test_sell_plan_invalidation_above_entry(self):
        """SELL plan should have invalidation > entry."""
        bars_1m = [
            {"ts": 1000, "low": 98, "high": 102, "close": 100, "open": 99},
            {"ts": 1060, "low": 97, "high": 101, "close": 98, "open": 100},
        ]
        consensus = ConsensusSignal(
            consensus_direction=-0.5,
            consensus_confidence=0.7,
            agreement_score=0.8,
            horizon_signals=[
                HorizonSignal(
                    horizon="1h",
                    direction_score=-0.5,
                    strength=0.6,
                    confidence=0.7,
                    features=FeatureSet("1h", 50, -0.4, 0.02, -1.0, 0.8, 98, 100, 2.0),
                    rationale=[],
                )
            ],
            rationale=[],
        )
        
        plan = generate_trade_plan(
            symbol="BTCUSDT",
            state=SignalState.SELL,
            confidence=0.7,
            consensus=consensus,
            bars_1m=bars_1m,
            rationale=["test"],
        )
        
        assert plan.state == SignalState.SELL
        assert plan.invalidation_price > plan.entry_price, "Stop-loss must be above entry for SELL"
        assert "short_position" in plan.rationale
    
    def test_neutral_no_entry_price(self):
        """NEUTRAL should have no entry price."""
        bars_1m = [
            {"ts": 1000, "low": 98, "high": 102, "close": 100, "open": 99},
        ]
        consensus = ConsensusSignal(
            consensus_direction=0.05,
            consensus_confidence=0.5,
            agreement_score=0.6,
            horizon_signals=[],
            rationale=[],
        )
        
        plan = generate_trade_plan(
            symbol="BTCUSDT",
            state=SignalState.NEUTRAL,
            confidence=0.5,
            consensus=consensus,
            bars_1m=bars_1m,
            rationale=["test"],
        )
        
        assert plan.state == SignalState.NEUTRAL
        assert plan.entry_price is None, "NEUTRAL should have no entry"
        assert "no_position_neutral" in plan.rationale
    
    def test_valid_until_in_future(self):
        """Valid until timestamp should be in the future."""
        import time
        
        bars_1m = [
            {"ts": 1000, "low": 98, "high": 102, "close": 100, "open": 99},
        ]
        consensus = ConsensusSignal(
            consensus_direction=0.5,
            consensus_confidence=0.7,
            agreement_score=0.8,
            horizon_signals=[
                HorizonSignal(
                    horizon="15m",
                    direction_score=0.5,
                    strength=0.6,
                    confidence=0.7,
                    features=FeatureSet("15m", 50, 0.4, 0.02, 1.0, 0.8, 102, 100, 2.0),
                    rationale=[],
                )
            ],
            rationale=[],
        )
        
        plan = generate_trade_plan(
            symbol="BTCUSDT",
            state=SignalState.BUY,
            confidence=0.7,
            consensus=consensus,
            bars_1m=bars_1m,
            rationale=[],
        )
        
        current_ts = int(time.time())
        assert plan.valid_until_ts > current_ts, "Valid until should be in the future"
        # For 15m horizon, should be ~4 hours in the future
        assert plan.valid_until_ts - current_ts > 3600, "Should have reasonable validity window"
    
    def test_sizing_monotonic_with_confidence(self):
        """Higher confidence should suggest larger (or equal) size."""
        bars_1m = [
            {"ts": 1000, "low": 98, "high": 102, "close": 100, "open": 99},
        ]
        consensus = ConsensusSignal(
            consensus_direction=0.5,
            consensus_confidence=0.5,
            agreement_score=0.8,
            horizon_signals=[],
            rationale=[],
        )
        
        plan_low = generate_trade_plan(
            symbol="BTCUSDT",
            state=SignalState.BUY,
            confidence=0.2,
            consensus=consensus,
            bars_1m=bars_1m,
            rationale=[],
        )
        
        plan_high = generate_trade_plan(
            symbol="BTCUSDT",
            state=SignalState.BUY,
            confidence=0.9,
            consensus=consensus,
            bars_1m=bars_1m,
            rationale=[],
        )
        
        assert plan_high.size_suggestion_pct >= plan_low.size_suggestion_pct, \
            "Higher confidence should not reduce size"

