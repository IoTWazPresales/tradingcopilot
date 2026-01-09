"""
Historical Binance klines fetcher for backtesting.

This module fetches historical data from Binance REST API and converts
it to the same format used by Phase 1 live streaming.
"""

import asyncio
import time
from datetime import datetime
from typing import List, Optional

import aiohttp

from ..storage.sqlite import BarRow


class BinanceHistoryFetcher:
    """
    Fetch historical klines from Binance REST API.
    
    Rate limits:
    - 1200 requests per minute (weight-based)
    - Each /klines request has weight=1
    - Max 1000 candles per request
    """
    
    def __init__(
        self,
        base_url: str = "https://api.binance.com",
        rate_limit_delay: float = 0.1,  # 100ms between requests = max 600/min (safe)
    ):
        self.base_url = base_url
        self.rate_limit_delay = rate_limit_delay
    
    async def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_ts: int,
        end_ts: int,
        limit: int = 1000,
    ) -> List[dict]:
        """
        Fetch klines for a single request (max 1000 candles).
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            interval: Timeframe (e.g., "1m", "5m", "1h")
            start_ts: Start timestamp (milliseconds)
            end_ts: End timestamp (milliseconds)
            limit: Max candles per request (default 1000)
            
        Returns:
            List of kline dicts
        """
        url = f"{self.base_url}/api/v3/klines"
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "startTime": start_ts,
            "endTime": end_ts,
            "limit": limit,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Binance API error {response.status}: {text}")
                
                data = await response.json()
                return data
    
    async def fetch_range(
        self,
        symbol: str,
        interval: str,
        start_dt: datetime,
        end_dt: datetime,
        progress_callback: Optional[callable] = None,
    ) -> List[BarRow]:
        """
        Fetch klines for a date range, handling pagination.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            interval: Timeframe (e.g., "1m", "5m", "1h")
            start_dt: Start datetime (UTC)
            end_dt: End datetime (UTC)
            progress_callback: Optional callback(fetched_count, total_estimated)
            
        Returns:
            List of BarRow objects in ascending time order
        """
        start_ts_ms = int(start_dt.timestamp() * 1000)
        end_ts_ms = int(end_dt.timestamp() * 1000)
        
        all_bars = []
        current_start = start_ts_ms
        
        while current_start < end_ts_ms:
            # Fetch batch
            klines = await self.fetch_klines(
                symbol=symbol,
                interval=interval,
                start_ts=current_start,
                end_ts=end_ts_ms,
                limit=1000,
            )
            
            if not klines:
                break  # No more data
            
            # Convert to BarRow
            for kline in klines:
                bar = self._convert_kline_to_bar(symbol, interval, kline)
                all_bars.append(bar)
            
            # Update progress
            if progress_callback:
                progress_callback(len(all_bars), None)
            
            # Move to next batch (start from last kline's close time + 1ms)
            last_close_time = klines[-1][6]  # Close time
            current_start = last_close_time + 1
            
            # Rate limit
            await asyncio.sleep(self.rate_limit_delay)
            
            # Safety: if we got less than 1000, we're done
            if len(klines) < 1000:
                break
        
        return all_bars
    
    def _convert_kline_to_bar(self, symbol: str, interval: str, kline: list) -> BarRow:
        """
        Convert Binance kline to BarRow.
        
        Binance kline format:
        [
          0: Open time (ms),
          1: Open,
          2: High,
          3: Low,
          4: Close,
          5: Volume,
          6: Close time (ms),
          7: Quote asset volume,
          8: Number of trades,
          9: Taker buy base asset volume,
          10: Taker buy quote asset volume,
          11: Ignore
        ]
        """
        return BarRow(
            symbol=symbol.upper(),
            interval=interval,
            ts=int(kline[0]) // 1000,  # Convert ms to seconds
            open=float(kline[1]),
            high=float(kline[2]),
            low=float(kline[3]),
            close=float(kline[4]),
            volume=float(kline[5]),
        )


async def backfill_to_store(
    store,
    symbol: str,
    interval: str,
    start_dt: datetime,
    end_dt: datetime,
    progress: bool = True,
    progress_cb=None,
) -> int:
    """
    Fetch historical data and write to SQLite store.
    
    Args:
        store: SQLiteStore instance
        symbol: Trading pair (e.g., "BTCUSDT")
        interval: Timeframe (e.g., "1m")
        start_dt: Start datetime (UTC)
        end_dt: End datetime (UTC)
        progress: Print progress messages (default True)
        progress_cb: Optional callback(msg: str) for progress updates
        
    Returns:
        Number of bars written
    """
    fetcher = BinanceHistoryFetcher()
    
    def internal_progress_cb(count, total):
        if progress and count % 5000 == 0:
            msg = f"Fetched {count} bars for {symbol} {interval}..."
            if progress_cb:
                progress_cb(msg)
            else:
                print(msg)
    
    if progress:
        msg = f"Fetching {symbol} {interval} from {start_dt} to {end_dt}..."
        if progress_cb:
            progress_cb(msg)
        else:
            print(msg)
    
    bars = await fetcher.fetch_range(
        symbol=symbol,
        interval=interval,
        start_dt=start_dt,
        end_dt=end_dt,
        progress_callback=internal_progress_cb if progress else None,
    )
    
    if progress:
        msg = f"Fetched {len(bars)} bars. Writing to database..."
        if progress_cb:
            progress_cb(msg)
        else:
            print(msg)
    
    count = await store.upsert_bars(bars)
    
    if progress:
        msg = f"✓ Wrote {count} bars to database"
        if progress_cb:
            progress_cb(msg)
        else:
            print(msg)
    
    return count


async def aggregate_to_higher_timeframes(
    store,
    symbol: str,
    source_interval: str = "1m",
    target_intervals: list[str] = None,
    progress: bool = True,
    progress_cb=None,
) -> int:
    """
    Aggregate existing bars from source interval to higher timeframes.
    
    Args:
        store: SQLiteStore instance
        symbol: Trading pair (e.g., "BTCUSDT")
        source_interval: Source interval (default "1m")
        target_intervals: List of target intervals (default ["5m", "15m", "1h", "4h", "1d", "1w"])
        progress: Print progress messages
        progress_cb: Optional callback(msg: str) for progress updates
        
    Returns:
        Total number of bars written across all intervals
    """
    from ..utils.timeframes import interval_to_seconds
    
    if target_intervals is None:
        target_intervals = ["5m", "15m", "1h", "4h", "1d", "1w"]
    
    if progress:
        msg = f"Aggregating {symbol} from {source_interval} to higher timeframes..."
        if progress_cb:
            progress_cb(msg)
        else:
            print(msg)
    
    # Fetch all source bars
    source_bars = await store.fetch_bars(symbol, source_interval, limit=1000000)
    
    if not source_bars:
        if progress:
            msg = f"No {source_interval} bars found for {symbol}. Skipping aggregation."
            if progress_cb:
                progress_cb(msg)
            else:
                print(msg)
        return 0
    
    total_written = 0
    
    for target_interval in target_intervals:
        target_seconds = interval_to_seconds(target_interval)
        source_seconds = interval_to_seconds(source_interval)
        
        if target_seconds <= source_seconds:
            continue  # Skip if target is not higher than source
        
        # Group source bars into target interval buckets
        aggregated = {}
        
        for bar in source_bars:
            # Calculate bucket start time
            bucket_start = (bar["ts"] // target_seconds) * target_seconds
            
            if bucket_start not in aggregated:
                aggregated[bucket_start] = {
                    "open": bar["open"],
                    "high": bar["high"],
                    "low": bar["low"],
                    "close": bar["close"],
                    "volume": bar["volume"],
                }
            else:
                # Update aggregated values
                agg = aggregated[bucket_start]
                agg["high"] = max(agg["high"], bar["high"])
                agg["low"] = min(agg["low"], bar["low"])
                agg["close"] = bar["close"]  # Latest close
                agg["volume"] += bar["volume"]
        
        # Convert to BarRow objects
        target_bars = []
        for ts, values in sorted(aggregated.items()):
            target_bars.append(BarRow(
                symbol=symbol,
                interval=target_interval,
                ts=ts,
                open=values["open"],
                high=values["high"],
                low=values["low"],
                close=values["close"],
                volume=values["volume"],
            ))
        
        # Upsert to database
        if target_bars:
            count = await store.upsert_bars(target_bars)
            total_written += count
            
            if progress:
                msg = f"  ✓ {target_interval}: {count} bars"
                if progress_cb:
                    progress_cb(msg)
                else:
                    print(msg)
    
    return total_written

