"""
End-to-end test for Phase 2 signal generation using REAL SQLite store.
This test does NOT use mocks - it creates a temporary database and tests the full pipeline.
"""

import asyncio
import tempfile
import time
from pathlib import Path

import pytest
import pytest_asyncio

from app.signals.engine import generate_signal
from app.storage.sqlite import SQLiteStore, BarRow


@pytest_asyncio.fixture
async def real_store_with_data():
    """Create a real SQLite store with deterministic test data."""
    # Create temporary database
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        # Initialize store
        store = SQLiteStore(db_path)
        await store.init()
        
        # Insert deterministic bars for BTCUSDT
        # Create an uptrend: prices from 100 to 125 over 50 bars
        base_ts = int(time.time()) - 3600  # 1 hour ago
        
        bars_1m = []
        for i in range(50):
            ts = base_ts + i * 60  # 1-minute intervals
            price = 100.0 + (i * 0.5)  # Steady uptrend
            bars_1m.append(BarRow(
                symbol="BTCUSDT",
                interval="1m",
                ts=ts,
                open=price - 0.2,
                high=price + 0.3,
                low=price - 0.3,
                close=price,
                volume=10.0 + i * 0.1,
            ))
        
        # Upsert 1m bars
        await store.upsert_bars(bars_1m)
        
        # Create aggregated 5m bars (10 bars, each covering 5 minutes)
        bars_5m = []
        for i in range(10):
            ts = base_ts + i * 300  # 5-minute intervals
            price = 100.0 + (i * 2.5)  # Steady uptrend
            bars_5m.append(BarRow(
                symbol="BTCUSDT",
                interval="5m",
                ts=ts,
                open=price - 0.5,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=50.0 + i * 2.0,
            ))
        
        await store.upsert_bars(bars_5m)
        
        # Create 15m bars (7 bars)
        bars_15m = []
        for i in range(7):
            ts = base_ts + i * 900  # 15-minute intervals
            price = 100.0 + (i * 3.5)
            bars_15m.append(BarRow(
                symbol="BTCUSDT",
                interval="15m",
                ts=ts,
                open=price - 1.0,
                high=price + 1.5,
                low=price - 1.5,
                close=price,
                volume=150.0 + i * 5.0,
            ))
        
        await store.upsert_bars(bars_15m)
        
        yield store
    
    finally:
        # Cleanup
        Path(db_path).unlink(missing_ok=True)


class TestSignalE2EWithRealSQLite:
    """End-to-end tests using real SQLite database."""
    
    @pytest.mark.asyncio
    async def test_signal_generation_with_real_data(self, real_store_with_data):
        """Test complete signal generation with real SQLite data."""
        store = real_store_with_data
        
        # Generate signal using real store
        response = await generate_signal(
            store=store,
            symbol="BTCUSDT",
            horizons=["1m", "5m", "15m"],
            bar_limit=100,
        )
        
        # Verify response structure
        assert response.symbol == "BTCUSDT"
        assert response.state in ["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]
        assert 0.0 <= response.confidence <= 1.0
        assert response.trade_plan is not None
        assert response.consensus is not None
        assert len(response.horizon_details) == 3  # 1m, 5m, 15m
        
        # Verify trade plan
        plan = response.trade_plan
        assert "state" in plan
        assert "confidence" in plan
        assert "invalidation_price" in plan
        assert "valid_until_ts" in plan
        assert "size_suggestion_pct" in plan
        assert "rationale" in plan
        
        # Verify confidence is reasonable (we have good data)
        assert response.confidence > 0.3, "Should have reasonable confidence with 50+ bars"
        
        # Verify consensus
        consensus = response.consensus
        assert "direction" in consensus
        assert "confidence" in consensus
        assert "agreement_score" in consensus
        assert -1.0 <= consensus["direction"] <= 1.0
        assert 0.0 <= consensus["confidence"] <= 1.0
        assert 0.0 <= consensus["agreement_score"] <= 1.0
    
    @pytest.mark.asyncio
    async def test_buy_signal_invalidation_logic(self, real_store_with_data):
        """Test that BUY signals have proper invalidation (stop-loss < entry)."""
        store = real_store_with_data
        
        response = await generate_signal(
            store=store,
            symbol="BTCUSDT",
            horizons=["1m", "5m", "15m"],
            bar_limit=100,
        )
        
        # With uptrend data, we should get BUY or STRONG_BUY
        assert response.state in ["BUY", "STRONG_BUY"], \
            f"Uptrend data should produce buy signal, got {response.state}"
        
        plan = response.trade_plan
        
        # Entry price should exist for BUY signal
        assert plan["entry_price"] is not None, "BUY signal should have entry price"
        
        # Invalidation should be below entry (stop-loss)
        assert plan["invalidation_price"] < plan["entry_price"], \
            f"BUY invalidation ({plan['invalidation_price']}) must be below entry ({plan['entry_price']})"
        
        # Invalidation should be reasonable (within 10% of entry)
        buffer_pct = (plan["entry_price"] - plan["invalidation_price"]) / plan["entry_price"]
        assert 0.01 < buffer_pct < 0.15, \
            f"Invalidation buffer should be 1-15%, got {buffer_pct*100:.1f}%"
    
    @pytest.mark.asyncio
    async def test_valid_until_is_future(self, real_store_with_data):
        """Test that valid_until_ts is in the future."""
        store = real_store_with_data
        
        current_ts = int(time.time())
        
        response = await generate_signal(
            store=store,
            symbol="BTCUSDT",
            horizons=["1m", "5m"],
            bar_limit=100,
        )
        
        plan = response.trade_plan
        assert plan["valid_until_ts"] > current_ts, \
            "valid_until should be in the future"
        
        # Should be reasonable window (at least 5 minutes, at most 1 day for these horizons)
        window = plan["valid_until_ts"] - current_ts
        assert 300 <= window <= 86400, \
            f"Validity window should be 5min-1day, got {window}s"
    
    @pytest.mark.asyncio
    async def test_size_suggestion_reasonable(self, real_store_with_data):
        """Test that size suggestion is within reasonable bounds."""
        store = real_store_with_data
        
        response = await generate_signal(
            store=store,
            symbol="BTCUSDT",
            horizons=["1m", "5m", "15m"],
            bar_limit=100,
        )
        
        plan = response.trade_plan
        size = plan["size_suggestion_pct"]
        
        # Size should be between 0.25% and 2.0% (per config)
        assert 0.2 <= size <= 2.1, \
            f"Size suggestion should be 0.25-2.0%, got {size}%"
    
    @pytest.mark.asyncio
    async def test_rationale_tags_present(self, real_store_with_data):
        """Test that rationale tags are provided."""
        store = real_store_with_data
        
        response = await generate_signal(
            store=store,
            symbol="BTCUSDT",
            horizons=["1m", "5m", "15m"],
            bar_limit=100,
        )
        
        # Trade plan should have rationale
        plan = response.trade_plan
        assert len(plan["rationale"]) > 0, "Should have rationale tags"
        
        # Consensus should have rationale
        consensus = response.consensus
        assert len(consensus["rationale"]) > 0, "Should have consensus rationale"
        
        # Each horizon should have rationale
        for horizon in response.horizon_details:
            assert len(horizon["rationale"]) > 0, \
                f"Horizon {horizon['horizon']} should have rationale"
    
    @pytest.mark.asyncio
    async def test_handles_missing_symbol_gracefully(self, real_store_with_data):
        """Test that missing symbol returns NEUTRAL with zero confidence."""
        store = real_store_with_data
        
        # Request signal for symbol with no data
        response = await generate_signal(
            store=store,
            symbol="NONEXISTENT",
            horizons=["1m", "5m"],
            bar_limit=100,
        )
        
        # Should return NEUTRAL
        assert response.state == "NEUTRAL"
        assert response.confidence == 0.0
        assert "no_data" in response.consensus["rationale"]
    
    @pytest.mark.asyncio
    async def test_multi_horizon_analysis_present(self, real_store_with_data):
        """Test that all requested horizons are analyzed."""
        store = real_store_with_data
        
        horizons = ["1m", "5m", "15m"]
        response = await generate_signal(
            store=store,
            symbol="BTCUSDT",
            horizons=horizons,
            bar_limit=100,
        )
        
        # Should have details for all horizons
        assert len(response.horizon_details) == len(horizons)
        
        # Check each horizon
        returned_horizons = {h["horizon"] for h in response.horizon_details}
        assert returned_horizons == set(horizons), \
            f"Expected horizons {horizons}, got {returned_horizons}"
        
        # Each horizon should have features
        for detail in response.horizon_details:
            assert "features" in detail
            features = detail["features"]
            assert "n_bars" in features
            assert "momentum" in features
            assert "volatility" in features
            assert features["n_bars"] > 0, "Should have fetched bars"

