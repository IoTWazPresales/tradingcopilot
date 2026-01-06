"""OANDA pricing stream implementation."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from collections import defaultdict
from typing import AsyncIterator

import aiohttp

from .base import Bar


logger = logging.getLogger(__name__)


class MinuteBarBuilder:
    """Build 1-minute OHLC bars from tick data."""
    
    def __init__(self, instrument: str):
        self.instrument = instrument
        self.current_minute: int | None = None
        self.open: float | None = None
        self.high: float | None = None
        self.low: float | None = None
        self.close: float | None = None
        
    def add_tick(self, price: float, ts_seconds: int) -> Bar | None:
        """
        Add a tick and return a finalized Bar if minute rolled over.
        
        Args:
            price: Mid price from bid/ask
            ts_seconds: Unix timestamp in seconds
            
        Returns:
            Finalized Bar for the previous minute, or None if still building
        """
        minute = ts_seconds // 60 * 60  # Floor to minute start
        
        # Initialize first minute
        if self.current_minute is None:
            self.current_minute = minute
            self.open = self.high = self.low = self.close = price
            return None
        
        # Still in same minute - update OHLC
        if minute == self.current_minute:
            if self.high is None or price > self.high:
                self.high = price
            if self.low is None or price < self.low:
                self.low = price
            self.close = price
            return None
        
        # Minute rolled over - finalize previous bar
        if self.open is None or self.high is None or self.low is None or self.close is None:
            # Should not happen, but defensive
            self.current_minute = minute
            self.open = self.high = self.low = self.close = price
            return None
        
        bar = Bar(
            symbol=self.instrument,
            interval="1m",
            ts=self.current_minute,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=0.0,  # OANDA does not provide volume on pricing stream
        )
        
        # Start new minute
        self.current_minute = minute
        self.open = self.high = self.low = self.close = price
        
        return bar


class OandaStreamingClient:
    """Streams pricing data from OANDA v20 API and builds 1m bars."""
    
    def __init__(
        self,
        instruments: list[str],
        api_key: str,
        account_id: str,
        environment: str = "practice",
    ):
        """
        Initialize OANDA streaming client.
        
        Args:
            instruments: List of instruments (e.g., ["EUR_USD", "GBP_USD"])
            api_key: OANDA API key
            account_id: OANDA account ID
            environment: "practice" or "live"
        """
        self.instruments = [i.upper() for i in instruments]
        self.api_key = api_key
        self.account_id = account_id
        self.environment = environment
        
        if environment == "practice":
            self.stream_url = f"https://stream-fxpractice.oanda.com/v3/accounts/{account_id}/pricing/stream"
        else:
            self.stream_url = f"https://stream-fxtrade.oanda.com/v3/accounts/{account_id}/pricing/stream"
        
        self.builders: dict[str, MinuteBarBuilder] = {}
        
    async def stream_bars(self) -> AsyncIterator[Bar]:
        """
        Stream 1m bars built from OANDA pricing ticks.
        
        Yields finalized 1m bars when minute rolls over.
        Handles reconnection with exponential backoff.
        """
        if not self.instruments:
            logger.warning("No OANDA instruments configured. OANDA stream not started.")
            return
        
        retry_count = 0
        max_retry_delay = 60
        
        # Initialize builders
        for instrument in self.instruments:
            self.builders[instrument] = MinuteBarBuilder(instrument)
        
        while True:
            try:
                params = {"instruments": ",".join(self.instruments)}
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept-Datetime-Format": "UNIX",
                }
                
                logger.info(f"Connecting to OANDA pricing stream: {self.instruments}")
                
                timeout = aiohttp.ClientTimeout(total=None, sock_read=90)
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(
                        self.stream_url,
                        params=params,
                        headers=headers,
                    ) as response:
                        if response.status != 200:
                            text = await response.text()
                            logger.error(f"OANDA stream error {response.status}: {text}")
                            raise Exception(f"OANDA returned {response.status}")
                        
                        retry_count = 0  # Reset on successful connection
                        logger.info(f"Connected to OANDA. Streaming {len(self.instruments)} instruments.")
                        
                        # Read streaming response line by line
                        async for line in response.content:
                            try:
                                line_str = line.decode("utf-8").strip()
                                if not line_str:
                                    continue
                                
                                data = json.loads(line_str)
                                
                                # Handle heartbeat
                                if data.get("type") == "HEARTBEAT":
                                    logger.debug("OANDA heartbeat received")
                                    continue
                                
                                # Handle price update
                                if data.get("type") == "PRICE":
                                    instrument = data.get("instrument")
                                    if not instrument or instrument not in self.builders:
                                        continue
                                    
                                    # Get timestamp
                                    time_str = data.get("time")
                                    if not time_str:
                                        continue
                                    
                                    # OANDA returns UNIX timestamp as string when Accept-Datetime-Format=UNIX
                                    try:
                                        ts_seconds = int(float(time_str))
                                    except (ValueError, TypeError):
                                        logger.warning(f"Invalid OANDA timestamp: {time_str}")
                                        continue
                                    
                                    # Calculate mid price from bids/asks
                                    bids = data.get("bids", [])
                                    asks = data.get("asks", [])
                                    
                                    if not bids and not asks:
                                        continue
                                    
                                    bid_price = float(bids[0]["price"]) if bids else None
                                    ask_price = float(asks[0]["price"]) if asks else None
                                    
                                    if bid_price is not None and ask_price is not None:
                                        mid_price = (bid_price + ask_price) / 2.0
                                    elif bid_price is not None:
                                        mid_price = bid_price
                                    elif ask_price is not None:
                                        mid_price = ask_price
                                    else:
                                        continue
                                    
                                    # Feed tick to builder
                                    builder = self.builders[instrument]
                                    bar = builder.add_tick(mid_price, ts_seconds)
                                    
                                    if bar is not None:
                                        yield bar
                            
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse OANDA message: {e}")
                            except KeyError as e:
                                logger.warning(f"Unexpected OANDA message format: {e}")
                            except Exception as e:
                                logger.error(f"Error processing OANDA message: {e}", exc_info=True)
            
            except aiohttp.ClientError as e:
                logger.error(f"OANDA connection error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error in OANDA stream: {e}", exc_info=True)
            
            # Exponential backoff with jitter
            retry_count += 1
            delay = min(2 ** retry_count + random.uniform(0, 1), max_retry_delay)
            logger.info(f"Reconnecting to OANDA in {delay:.1f}s (attempt {retry_count})...")
            await asyncio.sleep(delay)

