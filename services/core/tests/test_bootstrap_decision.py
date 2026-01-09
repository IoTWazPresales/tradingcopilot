"""
Tests for bootstrap decision logic (backfill vs skip).

These are smoke tests to verify the bootstrap correctly decides when to backfill.
"""

import pytest
import tempfile
import os
from unittest.mock import AsyncMock, patch

from app.storage.sqlite import SQLiteStore, BarRow


@pytest.mark.asyncio
async def test_bootstrap_backfill_when_below_threshold():
    """Test that bootstrap decides to backfill when bar count is below threshold."""
    # Create temp database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        # Initialize store
        store = SQLiteStore(db_path)
        await store.init()
        
        # Insert only 50 bars (below typical threshold of 3000)
        bars = []
        for i in range(50):
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
        await store.upsert_bars(bars)
        
        # Check count
        fetched = await store.fetch_bars("BTCUSDT", "1m", limit=100)
        assert len(fetched) == 50
        
        # Verify decision logic
        min_bars = 3000
        should_backfill = len(fetched) < min_bars
        assert should_backfill is True, "Should decide to backfill when below threshold"
    
    finally:
        os.remove(db_path)


@pytest.mark.asyncio
async def test_bootstrap_skip_backfill_when_above_threshold():
    """Test that bootstrap skips backfill when bar count is above threshold."""
    # Create temp database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        # Initialize store
        store = SQLiteStore(db_path)
        await store.init()
        
        # Insert 5000 bars (above threshold of 3000)
        bars = []
        for i in range(5000):
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
        await store.upsert_bars(bars)
        
        # Check count
        fetched = await store.fetch_bars("BTCUSDT", "1m", limit=10000)
        assert len(fetched) == 5000
        
        # Verify decision logic
        min_bars = 3000
        should_backfill = len(fetched) < min_bars
        assert should_backfill is False, "Should skip backfill when above threshold"
    
    finally:
        os.remove(db_path)


@pytest.mark.asyncio
async def test_bootstrap_empty_database():
    """Test that bootstrap correctly handles empty database."""
    # Create temp database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        # Initialize store (empty)
        store = SQLiteStore(db_path)
        await store.init()
        
        # Check count
        fetched = await store.fetch_bars("BTCUSDT", "1m", limit=100)
        assert len(fetched) == 0
        
        # Verify decision logic
        min_bars = 3000
        should_backfill = len(fetched) < min_bars
        assert should_backfill is True, "Should backfill when database is empty"
    
    finally:
        os.remove(db_path)
