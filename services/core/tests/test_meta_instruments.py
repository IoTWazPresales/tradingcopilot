"""
Tests for metadata API endpoint (Phase 7.1).

Tests the /v1/meta/instruments endpoint that provides UI with available symbols.
"""

import pytest
import tempfile
import os

from app.storage.sqlite import SQLiteStore, BarRow
from app.api.meta import get_instruments, set_store


@pytest.mark.asyncio
async def test_meta_instruments_basic():
    """Test basic instruments endpoint functionality."""
    # Create temp database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        # Initialize store
        store = SQLiteStore(db_path)
        await store.init()
        
        # Insert bars for BTCUSDT (multiple intervals)
        btc_bars = []
        for i in range(100):
            # 1m bars
            btc_bars.append(BarRow(
                symbol="BTCUSDT",
                interval="1m",
                ts=1000 + i * 60,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=10.0,
            ))
            # 5m bars (every 5 minutes)
            if i % 5 == 0:
                btc_bars.append(BarRow(
                    symbol="BTCUSDT",
                    interval="5m",
                    ts=1000 + i * 60,
                    open=100.0,
                    high=101.5,
                    low=98.5,
                    close=100.5,
                    volume=50.0,
                ))
        
        await store.upsert_bars(btc_bars)
        
        # Set store for API
        set_store(store)
        
        # Call endpoint (min_bars_1m=50)
        result = await get_instruments(min_bars_1m=50, store=store)
        
        # Assertions
        assert "symbols" in result
        assert "intervals" in result
        assert "counts" in result
        
        assert "BTCUSDT" in result["symbols"]
        assert "1m" in result["intervals"]
        assert "5m" in result["intervals"]
        
        assert result["counts"]["BTCUSDT"]["1m"] == 100
        assert result["counts"]["BTCUSDT"]["5m"] == 20  # 100 / 5
    
    finally:
        os.remove(db_path)


@pytest.mark.asyncio
async def test_meta_instruments_multiple_symbols():
    """Test instruments endpoint with multiple symbols."""
    # Create temp database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        # Initialize store
        store = SQLiteStore(db_path)
        await store.init()
        
        # Insert bars for BTCUSDT and ETHUSDT
        bars = []
        
        # BTCUSDT: 100 bars
        for i in range(100):
            bars.append(BarRow(
                symbol="BTCUSDT",
                interval="1m",
                ts=1000 + i * 60,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=10.0,
            ))
        
        # ETHUSDT: 80 bars
        for i in range(80):
            bars.append(BarRow(
                symbol="ETHUSDT",
                interval="1m",
                ts=1000 + i * 60,
                open=2000.0,
                high=2010.0,
                low=1990.0,
                close=2005.0,
                volume=5.0,
            ))
        
        await store.upsert_bars(bars)
        
        # Set store for API
        set_store(store)
        
        # Call endpoint (min_bars_1m=50)
        result = await get_instruments(min_bars_1m=50, store=store)
        
        # Both symbols should be present
        assert "BTCUSDT" in result["symbols"]
        assert "ETHUSDT" in result["symbols"]
        assert len(result["symbols"]) == 2
        
        # Check counts
        assert result["counts"]["BTCUSDT"]["1m"] == 100
        assert result["counts"]["ETHUSDT"]["1m"] == 80
    
    finally:
        os.remove(db_path)


@pytest.mark.asyncio
async def test_meta_instruments_min_bars_filter():
    """Test that min_bars_1m filter works correctly."""
    # Create temp database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        # Initialize store
        store = SQLiteStore(db_path)
        await store.init()
        
        # Insert bars
        bars = []
        
        # BTCUSDT: 100 bars (above threshold)
        for i in range(100):
            bars.append(BarRow(
                symbol="BTCUSDT",
                interval="1m",
                ts=1000 + i * 60,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=10.0,
            ))
        
        # ETHUSDT: 30 bars (below threshold of 50)
        for i in range(30):
            bars.append(BarRow(
                symbol="ETHUSDT",
                interval="1m",
                ts=1000 + i * 60,
                open=2000.0,
                high=2010.0,
                low=1990.0,
                close=2005.0,
                volume=5.0,
            ))
        
        await store.upsert_bars(bars)
        
        # Set store for API
        set_store(store)
        
        # Call endpoint (min_bars_1m=50)
        result = await get_instruments(min_bars_1m=50, store=store)
        
        # Only BTCUSDT should be present
        assert "BTCUSDT" in result["symbols"]
        assert "ETHUSDT" not in result["symbols"]
        assert len(result["symbols"]) == 1
    
    finally:
        os.remove(db_path)


@pytest.mark.asyncio
async def test_meta_instruments_empty_database():
    """Test instruments endpoint with empty database."""
    # Create temp database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        # Initialize store (empty)
        store = SQLiteStore(db_path)
        await store.init()
        
        # Set store for API
        set_store(store)
        
        # Call endpoint
        result = await get_instruments(min_bars_1m=50, store=store)
        
        # Should return empty lists
        assert result["symbols"] == []
        assert result["intervals"] == []
        assert result["counts"] == {}
    
    finally:
        os.remove(db_path)
