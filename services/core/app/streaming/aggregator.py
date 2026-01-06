"""Bar aggregation engine for building larger timeframes from 1m bars."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Iterable

from ..providers.base import Bar
from ..storage.sqlite import BarRow, SQLiteStore
from ..utils.timeframes import interval_to_seconds


logger = logging.getLogger(__name__)


class BarAggregator:
    """
    Aggregates 1m bars into larger timeframes and persists to storage.
    
    Maintains a rolling buffer of recent 1m bars per symbol and computes
    aggregate bars for configured intervals (5m, 15m, 1h, 4h, 1d, 1w).
    """
    
    def __init__(self, store: SQLiteStore, intervals: list[str]):
        """
        Initialize aggregator.
        
        Args:
            store: SQLite storage instance
            intervals: List of intervals to aggregate (e.g., ["1m", "5m", "15m", "1h"])
        """
        self.store = store
        self.intervals = intervals
        
        # Filter out intervals that aren't multiples of 1m or are < 1m
        self.aggregate_intervals = [i for i in intervals if i != "1m"]
        
        # Parse interval seconds for bucketing
        self.interval_seconds = {
            interval: interval_to_seconds(interval)
            for interval in self.aggregate_intervals
        }
        
        # Rolling buffer of 1m bars per symbol (keep last ~2000 bars = ~33 hours)
        self.buffers: dict[str, deque[Bar]] = defaultdict(lambda: deque(maxlen=2000))
        
        # Track last logged minute per symbol (for throttled logging)
        self._last_logged_minute: dict[str, int] = {}
        
        logger.info(f"BarAggregator initialized. Intervals: {intervals}")
    
    async def process_bar(self, bar: Bar) -> None:
        """
        Process a new 1m bar: store it and compute aggregates.
        
        Args:
            bar: A 1m bar from a provider
        """
        if bar.interval != "1m":
            logger.warning(f"Received non-1m bar: {bar.symbol} {bar.interval}. Skipping aggregation.")
            # Still store it as-is
            await self.store.upsert_bars([self._bar_to_row(bar)])
            return
        
        symbol = bar.symbol
        
        # Add to buffer
        self.buffers[symbol].append(bar)
        
        # Build list of bars to upsert
        bars_to_upsert = [self._bar_to_row(bar)]  # Original 1m bar
        
        # Compute aggregate bars for all configured intervals
        for interval in self.aggregate_intervals:
            agg_bar = self._aggregate_bar(symbol, interval, bar.ts)
            if agg_bar:
                bars_to_upsert.append(self._bar_to_row(agg_bar))
        
        # Batch upsert
        count = await self.store.upsert_bars(bars_to_upsert)
        
        # Log once per minute per symbol (throttled)
        current_minute = bar.ts // 60
        last_logged = self._last_logged_minute.get(symbol, 0)
        
        if current_minute > last_logged:
            self._last_logged_minute[symbol] = current_minute
            logger.info(
                f"{symbol} 1m bar stored: ts={bar.ts} "
                f"close={bar.close:.5f} volume={bar.volume:.2f} "
                f"(+{len(bars_to_upsert)-1} aggregated intervals)"
            )
    
    def _aggregate_bar(self, symbol: str, interval: str, latest_ts: int) -> Bar | None:
        """
        Aggregate 1m bars into a larger interval bar.
        
        Args:
            symbol: Symbol to aggregate
            interval: Target interval (e.g., "5m", "1h")
            latest_ts: Timestamp of the latest 1m bar (used to determine bucket)
            
        Returns:
            Aggregated Bar or None if insufficient data
        """
        if symbol not in self.buffers or not self.buffers[symbol]:
            return None
        
        interval_secs = self.interval_seconds[interval]
        
        # Determine the bucket start for the latest bar
        bucket_start = (latest_ts // interval_secs) * interval_secs
        bucket_end = bucket_start + interval_secs
        
        # Collect all 1m bars that fall within this bucket
        bars_in_bucket = [
            b for b in self.buffers[symbol]
            if bucket_start <= b.ts < bucket_end
        ]
        
        if not bars_in_bucket:
            return None
        
        # Sort by timestamp to ensure correct order
        bars_in_bucket.sort(key=lambda b: b.ts)
        
        # Aggregate OHLCV
        agg_open = bars_in_bucket[0].open
        agg_high = max(b.high for b in bars_in_bucket)
        agg_low = min(b.low for b in bars_in_bucket)
        agg_close = bars_in_bucket[-1].close
        agg_volume = sum(b.volume for b in bars_in_bucket)
        
        return Bar(
            symbol=symbol,
            interval=interval,
            ts=bucket_start,
            open=agg_open,
            high=agg_high,
            low=agg_low,
            close=agg_close,
            volume=agg_volume,
        )
    
    @staticmethod
    def _bar_to_row(bar: Bar) -> BarRow:
        """Convert Bar to BarRow for storage."""
        return BarRow(
            symbol=bar.symbol,
            interval=bar.interval,
            ts=bar.ts,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
        )

