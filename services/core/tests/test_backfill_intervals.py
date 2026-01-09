"""
Tests for multi-interval backfill and aggregation.

Verifies that 1m bars are correctly aggregated to higher timeframes.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta

from app.storage.sqlite import SQLiteStore, BarRow
from app.backtest.binance_history import aggregate_to_higher_timeframes


@pytest.mark.asyncio
async def test_aggregate_1m_to_5m():
    """Test aggregation from 1m to 5m bars."""
    # Create temp database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        # Initialize store
        store = SQLiteStore(db_path)
        await store.init()
        
        # Insert 10 consecutive 1m bars (2 complete 5m bars)
        bars_1m = []
        base_ts = 1000
        
        for i in range(10):
            bars_1m.append(BarRow(
                symbol="BTCUSDT",
                interval="1m",
                ts=base_ts + i * 60,
                open=100.0 + i,
                high=101.0 + i,
                low=99.0 + i,
                close=100.5 + i,
                volume=10.0,
            ))
        
        await store.upsert_bars(bars_1m)
        
        # Aggregate to 5m
        count = await aggregate_to_higher_timeframes(
            store=store,
            symbol="BTCUSDT",
            source_interval="1m",
            target_intervals=["5m"],
            progress=False
        )
        
        assert count > 0, "Should have created 5m bars"
        
        # Fetch 5m bars
        bars_5m = await store.fetch_bars("BTCUSDT", "5m", limit=10)
        
        # Should have 2 complete 5m bars
        assert len(bars_5m) == 2, f"Expected 2 5m bars, got {len(bars_5m)}"
        
        # Verify first 5m bar aggregates first 5 1m bars
        first_5m = bars_5m[0]
        assert first_5m["open"] == 100.0, "First 5m open should be first 1m open"
        assert first_5m["high"] == 104.0, "First 5m high should be max of first 5 1m highs"
        assert first_5m["low"] == 99.0, "First 5m low should be min of first 5 1m lows"
        assert first_5m["close"] == 104.5, "First 5m close should be last 1m close"
        assert first_5m["volume"] == 50.0, "First 5m volume should be sum of first 5 1m volumes"
    
    finally:
        os.remove(db_path)


@pytest.mark.asyncio
async def test_aggregate_to_multiple_intervals():
    """Test aggregation to multiple intervals at once."""
    # Create temp database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        # Initialize store
        store = SQLiteStore(db_path)
        await store.init()
        
        # Insert 60 consecutive 1m bars (1 hour)
        bars_1m = []
        base_ts = 1000
        
        for i in range(60):
            bars_1m.append(BarRow(
                symbol="BTCUSDT",
                interval="1m",
                ts=base_ts + i * 60,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=10.0,
            ))
        
        await store.upsert_bars(bars_1m)
        
        # Aggregate to 5m, 15m, 1h
        count = await aggregate_to_higher_timeframes(
            store=store,
            symbol="BTCUSDT",
            source_interval="1m",
            target_intervals=["5m", "15m", "1h"],
            progress=False
        )
        
        assert count > 0, "Should have created aggregated bars"
        
        # Verify counts
        bars_5m = await store.fetch_bars("BTCUSDT", "5m", limit=100)
        bars_15m = await store.fetch_bars("BTCUSDT", "15m", limit=100)
        bars_1h = await store.fetch_bars("BTCUSDT", "1h", limit=100)
        
        assert len(bars_5m) == 12, f"Expected 12 5m bars (60/5), got {len(bars_5m)}"
        assert len(bars_15m) == 4, f"Expected 4 15m bars (60/15), got {len(bars_15m)}"
        assert len(bars_1h) == 1, f"Expected 1 1h bar (60/60), got {len(bars_1h)}"
    
    finally:
        os.remove(db_path)


@pytest.mark.asyncio
async def test_aggregate_empty_source():
    """Test aggregation with no source bars."""
    # Create temp database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        # Initialize store (empty)
        store = SQLiteStore(db_path)
        await store.init()
        
        # Try to aggregate (should handle gracefully)
        count = await aggregate_to_higher_timeframes(
            store=store,
            symbol="BTCUSDT",
            source_interval="1m",
            target_intervals=["5m"],
            progress=False
        )
        
        assert count == 0, "Should return 0 for empty source"
        
        # Verify no 5m bars were created
        bars_5m = await store.fetch_bars("BTCUSDT", "5m", limit=10)
        assert len(bars_5m) == 0, "Should not create bars from empty source"
    
    finally:
        os.remove(db_path)


@pytest.mark.asyncio
async def test_aggregate_preserves_ohlc_logic():
    """Test that aggregation preserves OHLC semantics."""
    # Create temp database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        # Initialize store
        store = SQLiteStore(db_path)
        await store.init()
        
        # Insert 5 1m bars with specific values to test OHLC logic
        bars_1m = [
            BarRow("BTCUSDT", "1m", 1000, open=100, high=105, low=99, close=102, volume=10),
            BarRow("BTCUSDT", "1m", 1060, open=102, high=108, low=101, close=107, volume=20),
            BarRow("BTCUSDT", "1m", 1120, open=107, high=110, low=106, close=109, volume=15),
            BarRow("BTCUSDT", "1m", 1180, open=109, high=112, low=108, close=111, volume=25),
            BarRow("BTCUSDT", "1m", 1240, open=111, high=115, low=110, close=114, volume=30),
        ]
        
        await store.upsert_bars(bars_1m)
        
        # Aggregate to 5m
        await aggregate_to_higher_timeframes(
            store=store,
            symbol="BTCUSDT",
            source_interval="1m",
            target_intervals=["5m"],
            progress=False
        )
        
        # Fetch 5m bar
        bars_5m = await store.fetch_bars("BTCUSDT", "5m", limit=1)
        assert len(bars_5m) == 1
        
        bar_5m = bars_5m[0]
        
        # Open should be first bar's open
        assert bar_5m["open"] == 100
        
        # High should be highest of all highs
        assert bar_5m["high"] == 115
        
        # Low should be lowest of all lows
        assert bar_5m["low"] == 99
        
        # Close should be last bar's close
        assert bar_5m["close"] == 114
        
        # Volume should be sum
        assert bar_5m["volume"] == 100  # 10+20+15+25+30
    
    finally:
        os.remove(db_path)
