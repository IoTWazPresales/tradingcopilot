"""Tests for historical backfill functionality."""

import pytest
from datetime import datetime, timedelta

from app.backtest.binance_history import BinanceHistoryFetcher
from app.storage.sqlite import BarRow


class TestBinanceHistoryFetcher:
    """Tests for BinanceHistoryFetcher."""
    
    def test_convert_kline_to_bar(self):
        """Test kline conversion to BarRow."""
        fetcher = BinanceHistoryFetcher()
        
        # Sample Binance kline
        kline = [
            1609459200000,  # Open time (ms)
            "29000.00",     # Open
            "29500.00",     # High
            "28800.00",     # Low
            "29200.00",     # Close
            "123.45",       # Volume
            1609459259999,  # Close time (ms)
            "3600000.00",   # Quote asset volume
            500,            # Number of trades
            "60.00",        # Taker buy base asset volume
            "1800000.00",   # Taker buy quote asset volume
            "0"             # Ignore
        ]
        
        bar = fetcher._convert_kline_to_bar("BTCUSDT", "1m", kline)
        
        assert bar.symbol == "BTCUSDT"
        assert bar.interval == "1m"
        assert bar.ts == 1609459200  # Converted from ms to seconds
        assert bar.open == 29000.00
        assert bar.high == 29500.00
        assert bar.low == 28800.00
        assert bar.close == 29200.00
        assert bar.volume == 123.45
    
    def test_convert_kline_normalizes_symbol(self):
        """Symbol should be uppercase."""
        fetcher = BinanceHistoryFetcher()
        
        kline = [1609459200000, "100", "101", "99", "100.5", "10", 1609459259999, "0", 0, "0", "0", "0"]
        bar = fetcher._convert_kline_to_bar("btcusdt", "1m", kline)
        
        assert bar.symbol == "BTCUSDT"
    
    @pytest.mark.asyncio
    async def test_fetch_range_empty(self):
        """Test fetching when no data available (mock)."""
        fetcher = BinanceHistoryFetcher()
        
        # Mock fetch_klines to return empty list
        async def mock_fetch_klines(*args, **kwargs):
            return []
        
        fetcher.fetch_klines = mock_fetch_klines
        
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 2)
        
        bars = await fetcher.fetch_range("BTCUSDT", "1m", start, end)
        
        assert bars == []
    
    @pytest.mark.asyncio
    async def test_fetch_range_single_batch(self):
        """Test fetching single batch of data."""
        fetcher = BinanceHistoryFetcher(rate_limit_delay=0.0)  # No delay for testing
        
        # Mock fetch_klines to return one batch
        async def mock_fetch_klines(*args, **kwargs):
            return [
                [1609459200000, "100", "101", "99", "100.5", "10", 1609459259999, "0", 0, "0", "0", "0"],
                [1609459260000, "100.5", "102", "100", "101", "11", 1609459319999, "0", 0, "0", "0", "0"],
            ]
        
        fetcher.fetch_klines = mock_fetch_klines
        
        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 2)
        
        bars = await fetcher.fetch_range("BTCUSDT", "1m", start, end)
        
        assert len(bars) == 2
        assert bars[0].symbol == "BTCUSDT"
        assert bars[0].close == 100.5
        assert bars[1].close == 101.0
    
    @pytest.mark.asyncio
    async def test_fetch_range_pagination(self):
        """Test pagination when data exceeds 1000 candles."""
        fetcher = BinanceHistoryFetcher(rate_limit_delay=0.0)
        
        call_count = 0
        
        # Mock fetch_klines to return multiple batches
        async def mock_fetch_klines(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                # First batch: 1000 candles
                return [
                    [1609459200000 + i * 60000, "100", "101", "99", "100", "10", 
                     1609459259999 + i * 60000, "0", 0, "0", "0", "0"]
                    for i in range(1000)
                ]
            elif call_count == 2:
                # Second batch: 500 candles (less than 1000, so pagination stops)
                return [
                    [1609459200000 + (1000 + i) * 60000, "100", "101", "99", "100", "10",
                     1609459259999 + (1000 + i) * 60000, "0", 0, "0", "0", "0"]
                    for i in range(500)
                ]
            else:
                return []
        
        fetcher.fetch_klines = mock_fetch_klines
        
        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 10)
        
        bars = await fetcher.fetch_range("BTCUSDT", "1m", start, end)
        
        assert len(bars) == 1500  # 1000 + 500
        assert call_count == 2  # Two API calls
    
    @pytest.mark.asyncio
    async def test_fetch_range_progress_callback(self):
        """Test progress callback is called."""
        fetcher = BinanceHistoryFetcher(rate_limit_delay=0.0)
        
        # Mock fetch_klines
        async def mock_fetch_klines(*args, **kwargs):
            return [
                [1609459200000, "100", "101", "99", "100", "10", 1609459259999, "0", 0, "0", "0", "0"],
            ]
        
        fetcher.fetch_klines = mock_fetch_klines
        
        progress_calls = []
        
        def progress_cb(count, total):
            progress_calls.append(count)
        
        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 2)
        
        bars = await fetcher.fetch_range("BTCUSDT", "1m", start, end, progress_callback=progress_cb)
        
        assert len(bars) == 1
        assert len(progress_calls) == 1  # Progress callback was called
        assert progress_calls[0] == 1  # Called with count=1

