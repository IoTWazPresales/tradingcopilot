"""
Tests for AUTO WS→REST fallback functionality.

Verifies that when WebSocket fails, the system seamlessly falls back
to REST polling without crashing.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.streaming.runner import StreamingRunner
from app.config import Settings
from app.storage.sqlite import SQLiteStore


class MockWebSocketFailure:
    """Mock WebSocket that always fails."""
    
    def __init__(self, *args, **kwargs):
        pass
    
    async def stream_bars(self):
        """Simulate immediate WebSocket failure."""
        # Yield nothing, then raise exception
        if False:
            yield None  # Make this a generator
        raise ConnectionError("WebSocket connection failed")


class MockRESTPoller:
    """Mock REST poller that works."""
    
    def __init__(self, *args, **kwargs):
        pass
    
    async def stream_bars(self):
        """Simulate working REST poller."""
        # Yield a few bars then stop
        for i in range(3):
            from app.providers.base import Bar
            yield Bar(
                symbol="BTCUSDT",
                interval="1m",
                ts=1000 + i * 60,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=10.0
            )
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_auto_fallback_on_ws_failure(tmp_path):
    """Test that AUTO mode falls back to REST when WS fails."""
    # Create temp database
    db_path = tmp_path / "test.db"
    
    # Create store
    store = SQLiteStore(str(db_path))
    await store.init()
    
    # Create settings with AUTO mode
    settings = Settings(
        sqlite_path=str(db_path),
        providers="binance",
        binance_symbols="btcusdt",
        binance_transport="auto",
        binance_rest_poll_seconds=0.1,  # Fast polling for test
    )
    
    # Create runner
    runner = StreamingRunner(settings, store)
    
    # Mock the WebSocket and REST providers
    with patch('app.streaming.runner.BinanceWebSocketStreamer', MockWebSocketFailure):
        with patch('app.streaming.runner.BinanceRESTPoller', MockRESTPoller):
            # Start runner
            await runner.start()
            
            # Give it time to process
            await asyncio.sleep(0.2)
            
            # Stop runner
            await runner.stop()
    
    # Verify that REST fallback was triggered
    assert runner._rest_fallback_triggered is True, "REST fallback should have been triggered"
    
    # Verify that bars were written (from REST)
    bars = await store.fetch_bars("BTCUSDT", "1m", limit=10)
    assert len(bars) > 0, "Bars should have been written by REST fallback"


@pytest.mark.asyncio
async def test_rest_mode_no_ws_attempt(tmp_path):
    """Test that REST mode doesn't attempt WebSocket."""
    # Create temp database
    db_path = tmp_path / "test.db"
    
    # Create store
    store = SQLiteStore(str(db_path))
    await store.init()
    
    # Create settings with REST mode
    settings = Settings(
        sqlite_path=str(db_path),
        providers="binance",
        binance_symbols="btcusdt",
        binance_transport="rest",
        binance_rest_poll_seconds=0.1,
    )
    
    # Create runner
    runner = StreamingRunner(settings, store)
    
    # Mock REST poller
    with patch('app.streaming.runner.BinanceRESTPoller', MockRESTPoller):
        # Start runner
        await runner.start()
        
        # Give it time to process
        await asyncio.sleep(0.2)
        
        # Stop runner
        await runner.stop()
    
    # Verify REST was used (no fallback because we started with REST)
    assert runner._rest_fallback_triggered is False, "Should not trigger fallback in REST mode"
    assert runner.active_binance_transport == "rest"
    
    # Verify bars were written
    bars = await store.fetch_bars("BTCUSDT", "1m", limit=10)
    assert len(bars) > 0, "Bars should have been written by REST"


@pytest.mark.asyncio
async def test_runner_continues_after_ws_death(tmp_path):
    """Test that runner continues running after WS consumer dies."""
    # Create temp database
    db_path = tmp_path / "test.db"
    
    # Create store
    store = SQLiteStore(str(db_path))
    await store.init()
    
    # Create settings
    settings = Settings(
        sqlite_path=str(db_path),
        providers="binance",
        binance_symbols="btcusdt",
        binance_transport="auto",
    )
    
    # Create runner
    runner = StreamingRunner(settings, store)
    
    # Mock WS to fail and REST to work
    with patch('app.streaming.runner.BinanceWebSocketStreamer', MockWebSocketFailure):
        with patch('app.streaming.runner.BinanceRESTPoller', MockRESTPoller):
            await runner.start()
            
            # Verify at least one task is running
            assert len(runner.tasks) > 0
            
            # Wait for fallback
            await asyncio.sleep(0.3)
            
            # Runner should still be alive
            assert runner._rest_fallback_triggered is True
            
            await runner.stop()
