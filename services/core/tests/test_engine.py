"""Integration tests for signal engine."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

from app.signals.engine import generate_signal
from app.signals.types import SignalState


@pytest_asyncio.fixture
async def mock_store():
    """Create a mock store with test data."""
    store = AsyncMock()
    
    # Mock fetch_bars to return bullish 1m data
    async def fetch_bars_mock(symbol, interval, limit):
        if interval == "1m":
            return [
                {"ts": 1000 + i*60, "open": 100 + i*0.5, "high": 101 + i*0.5,
                 "low": 99 + i*0.5, "close": 100.5 + i*0.5, "volume": 10}
                for i in range(50)
            ]
        elif interval == "15m":
            return [
                {"ts": 1000 + i*900, "open": 100 + i*2, "high": 102 + i*2,
                 "low": 98 + i*2, "close": 101 + i*2, "volume": 100}
                for i in range(40)
            ]
        elif interval == "1h":
            return [
                {"ts": 1000 + i*3600, "open": 100 + i*5, "high": 105 + i*5,
                 "low": 95 + i*5, "close": 103 + i*5, "volume": 400}
                for i in range(48)
            ]
        else:
            return []
    
    store.fetch_bars = fetch_bars_mock
    return store


class TestGenerateSignal:
    """Integration tests for generate_signal."""
    
    @pytest.mark.asyncio
    async def test_returns_signal_response(self, mock_store):
        """Should return complete SignalResponse."""
        response = await generate_signal(
            store=mock_store,
            symbol="BTCUSDT",
            horizons=["1m", "15m", "1h"],
            bar_limit=100,
        )
        
        assert response.symbol == "BTCUSDT"
        assert response.state in ["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]
        assert 0.0 <= response.confidence <= 1.0
        assert response.trade_plan is not None
        assert response.consensus is not None
        assert len(response.horizon_details) == 3
    
    @pytest.mark.asyncio
    async def test_bullish_data_gives_buy_signal(self, mock_store):
        """Uptrending data should produce BUY or STRONG_BUY."""
        response = await generate_signal(
            store=mock_store,
            symbol="BTCUSDT",
            horizons=["1m", "15m", "1h"],
            bar_limit=100,
        )
        
        # With consistent uptrend across horizons, should be bullish
        assert response.state in ["BUY", "STRONG_BUY"], \
            f"Bullish data should produce buy signal, got {response.state}"
    
    @pytest.mark.asyncio
    async def test_trade_plan_included(self, mock_store):
        """Trade plan should have all required fields."""
        response = await generate_signal(
            store=mock_store,
            symbol="BTCUSDT",
            horizons=["1m", "1h"],
            bar_limit=100,
        )
        
        plan = response.trade_plan
        assert "state" in plan
        assert "confidence" in plan
        assert "invalidation_price" in plan
        assert "valid_until_ts" in plan
        assert "size_suggestion_pct" in plan
        assert "rationale" in plan
    
    @pytest.mark.asyncio
    async def test_handles_missing_data(self, mock_store):
        """Should handle symbols with no data gracefully."""
        async def fetch_bars_empty(symbol, interval, limit):
            return []
        
        mock_store.fetch_bars = fetch_bars_empty
        
        response = await generate_signal(
            store=mock_store,
            symbol="UNKNOWN",
            horizons=["1m", "1h"],
            bar_limit=100,
        )
        
        # Should return NEUTRAL with low confidence when no data
        assert response.state == "NEUTRAL"
        assert response.confidence == 0.0

