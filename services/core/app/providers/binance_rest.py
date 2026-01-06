"""Binance REST polling implementation (fallback for networks blocking WebSocket)."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

import aiohttp

from .base import Bar


logger = logging.getLogger(__name__)


class BinanceRESTPoller:
    """Polls Binance REST API for 1m klines when WebSocket is unavailable."""
    
    def __init__(self, symbols: list[str], poll_seconds: float = 2.0):
        """
        Initialize Binance REST poller.
        
        Args:
            symbols: List of symbols in lowercase (e.g., ["btcusdt", "ethusdt"])
            poll_seconds: Polling interval in seconds
        """
        self.symbols = [s.lower() for s in symbols]
        self.poll_seconds = max(1.0, poll_seconds)  # Minimum 1 second
        self.base_url = "https://api.binance.com/api/v3/klines"
        self._last_emitted: dict[str, int] = {}  # Track last emitted timestamp per symbol
        
    async def stream_bars(self) -> AsyncIterator[Bar]:
        """
        Poll Binance REST API and yield 1m bars.
        
        IMPORTANT: The most recent kline is often still OPEN. We only emit the
        last CLOSED kline (index -2, second from last).
        
        Yields finalized 1m bars with deduplication.
        """
        if not self.symbols:
            logger.warning("No Binance symbols configured. Binance REST poller not started.")
            return
        
        logger.info(
            f"Starting Binance REST poller for {len(self.symbols)} symbols "
            f"(poll interval: {self.poll_seconds}s)"
        )
        
        timeout = aiohttp.ClientTimeout(total=10)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while True:
                try:
                    # Poll each symbol
                    for symbol_lower in self.symbols:
                        try:
                            bar = await self._fetch_latest_closed_bar(session, symbol_lower)
                            if bar:
                                # Deduplicate: only emit if we haven't seen this timestamp before
                                symbol_upper = symbol_lower.upper()
                                last_ts = self._last_emitted.get(symbol_upper, 0)
                                
                                if bar.ts > last_ts:
                                    self._last_emitted[symbol_upper] = bar.ts
                                    yield bar
                        
                        except Exception as e:
                            logger.warning(f"Error fetching {symbol_lower}: {e}")
                    
                    # Wait before next poll cycle
                    await asyncio.sleep(self.poll_seconds)
                
                except asyncio.CancelledError:
                    logger.info("Binance REST poller cancelled.")
                    raise
                except Exception as e:
                    logger.error(f"Unexpected error in REST poller: {e}", exc_info=True)
                    await asyncio.sleep(5)  # Brief pause before retrying
    
    async def _fetch_latest_closed_bar(
        self,
        session: aiohttp.ClientSession,
        symbol_lower: str,
    ) -> Bar | None:
        """
        Fetch the latest closed 1m bar for a symbol.
        
        Args:
            session: aiohttp session
            symbol_lower: Symbol in lowercase (e.g., "btcusdt")
            
        Returns:
            Bar object for the last closed kline, or None on error
        """
        symbol_upper = symbol_lower.upper()
        
        params = {
            "symbol": symbol_upper,
            "interval": "1m",
            "limit": 2,  # Get last 2 klines: [-2] is closed, [-1] is current/open
        }
        
        try:
            async with session.get(self.base_url, params=params) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.warning(f"Binance API error {response.status} for {symbol_upper}: {text}")
                    return None
                
                data = await response.json()
                
                if not data or len(data) < 2:
                    logger.warning(f"Insufficient kline data for {symbol_upper}: got {len(data)} klines")
                    return None
                
                # Use second-to-last kline (index -2) - this is the last CLOSED bar
                kline = data[-2]
                
                # Kline format: [open_time, open, high, low, close, volume, close_time, ...]
                bar = Bar(
                    symbol=symbol_upper,
                    interval="1m",
                    ts=int(kline[0]) // 1000,  # open_time in ms -> seconds
                    open=float(kline[1]),
                    high=float(kline[2]),
                    low=float(kline[3]),
                    close=float(kline[4]),
                    volume=float(kline[5]),
                )
                
                return bar
        
        except aiohttp.ClientError as e:
            logger.warning(f"Network error fetching {symbol_upper}: {e}")
            return None
        except (KeyError, IndexError, ValueError) as e:
            logger.warning(f"Error parsing kline data for {symbol_upper}: {e}")
            return None

