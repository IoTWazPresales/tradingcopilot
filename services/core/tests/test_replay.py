"""Tests for replay functionality."""

import pytest
import pytest_asyncio
import tempfile
from pathlib import Path
from datetime import datetime

from app.backtest.replay import ReplayRunner, ReplayEvent
from app.storage.sqlite import SQLiteStore, BarRow


@pytest_asyncio.fixture
async def replay_store_with_data():
    """Create store with deterministic replay data."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        store = SQLiteStore(db_path)
        await store.init()
        
        # Insert 50 1m bars (uptrend)
        base_ts = int(datetime(2026, 1, 1).timestamp())
        bars = []
        for i in range(50):
            bars.append(BarRow(
                symbol="BTCUSDT",
                interval="1m",
                ts=base_ts + i * 60,
                open=100.0 + i * 0.5,
                high=101.0 + i * 0.5,
                low=99.0 + i * 0.5,
                close=100.5 + i * 0.5,
                volume=10.0,
            ))
        
        await store.upsert_bars(bars)
        
        yield store
    
    finally:
        Path(db_path).unlink(missing_ok=True)


class TestReplayEvent:
    """Tests for ReplayEvent."""
    
    def test_to_dict(self):
        """Test ReplayEvent serialization."""
        event = ReplayEvent(
            ts=1609459200,
            symbol="BTCUSDT",
            horizons=["1m", "5m"],
            state="BUY",
            confidence=0.75,
            entry_price=100.0,
            invalidation_price=98.0,
            valid_until_ts=1609460000,
            size_suggestion_pct=1.0,
            consensus_direction=0.5,
            agreement_score=0.85,
        )
        
        d = event.to_dict()
        
        assert d["symbol"] == "BTCUSDT"
        assert d["state"] == "BUY"
        assert d["confidence"] == 0.75


class TestReplayRunner:
    """Tests for ReplayRunner."""
    
    @pytest.mark.asyncio
    async def test_replay_generates_events(self, replay_store_with_data):
        """Test that replay generates events from data."""
        store = replay_store_with_data
        
        base_ts = int(datetime(2026, 1, 1).timestamp())
        
        runner = ReplayRunner(
            store=store,
            symbol="BTCUSDT",
            horizons=["1m"],
            start_ts=base_ts,
            end_ts=base_ts + 600,  # 10 minutes
            bar_limit=50,
            include_explanation=False,
        )
        
        events = await runner.run(progress=False)
        
        # Should generate events (exact count depends on data availability)
        assert len(events) > 0
        assert all(e.symbol == "BTCUSDT" for e in events)
    
    @pytest.mark.asyncio
    async def test_replay_deterministic(self, replay_store_with_data):
        """Test that replay produces deterministic results."""
        store = replay_store_with_data
        
        base_ts = int(datetime(2026, 1, 1).timestamp())
        
        runner = ReplayRunner(
            store=store,
            symbol="BTCUSDT",
            horizons=["1m"],
            start_ts=base_ts,
            end_ts=base_ts + 300,
            bar_limit=50,
        )
        
        events1 = await runner.run(progress=False)
        events2 = await runner.run(progress=False)
        
        # Same input → same output
        assert len(events1) == len(events2)
        if events1:
            assert events1[0].state == events2[0].state
            assert events1[0].confidence == events2[0].confidence
    
    def test_save_to_jsonl(self, tmp_path):
        """Test saving events to JSONL."""
        events = [
            ReplayEvent(
                ts=1000,
                symbol="BTCUSDT",
                horizons=["1m"],
                state="BUY",
                confidence=0.7,
                entry_price=100.0,
                invalidation_price=98.0,
                valid_until_ts=2000,
                size_suggestion_pct=1.0,
                consensus_direction=0.5,
                agreement_score=0.8,
            )
        ]
        
        output_path = tmp_path / "test.jsonl"
        
        runner = ReplayRunner(
            store=None,  # Not needed for save
            symbol="BTCUSDT",
            horizons=["1m"],
            start_ts=0,
            end_ts=1000,
        )
        
        runner.save_to_jsonl(events, output_path)
        
        assert output_path.exists()
        content = output_path.read_text()
        assert "BTCUSDT" in content
        assert "BUY" in content

