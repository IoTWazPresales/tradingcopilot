"""Binance WebSocket streaming implementation."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import AsyncIterator

import websockets
from websockets.client import WebSocketClientProtocol

from .base import Bar


logger = logging.getLogger(__name__)


class BinanceWsUnavailable(Exception):
    """Raised when Binance WebSocket is unavailable after multiple connection attempts."""
    pass


class BinanceWebSocketStreamer:
    """Streams 1m klines from Binance WebSocket API."""
    
    def __init__(self, symbols: list[str], fail_fast: bool = False):
        """
        Initialize Binance WebSocket streamer.
        
        Args:
            symbols: List of symbols in lowercase (e.g., ["btcusdt", "ethusdt"])
            fail_fast: If True, raise BinanceWsUnavailable after 3 consecutive handshake failures
        """
        self.symbols = [s.lower() for s in symbols]
        self.base_url = "wss://stream.binance.com:9443/ws"
        self._ws: WebSocketClientProtocol | None = None
        self.fail_fast = fail_fast
        self.consecutive_handshake_failures = 0
        
    async def stream_bars(self) -> AsyncIterator[Bar]:
        """
        Stream 1m bars from Binance.
        
        Yields finalized 1m bars when kline.x (is_final) is true.
        Handles reconnection with exponential backoff.
        """
        if not self.symbols:
            logger.warning("No Binance symbols configured. Binance stream not started.")
            return
        
        retry_count = 0
        max_retry_delay = 60
        
        while True:
            try:
                # Build subscription streams
                streams = [f"{symbol}@kline_1m" for symbol in self.symbols]
                stream_names = "/".join(streams)
                url = f"{self.base_url}/{stream_names}"
                
                logger.info(f"Connecting to Binance WebSocket: {self.symbols}")
                
                # Add explicit timeouts for Windows network environments
                async with websockets.connect(
                    url,
                    open_timeout=10,
                    close_timeout=10,
                    ping_interval=20,
                    ping_timeout=20,
                ) as ws:
                    self._ws = ws
                    retry_count = 0  # Reset retry count on successful connection
                    self.consecutive_handshake_failures = 0  # Reset handshake failure counter
                    logger.info(f"Connected to Binance WebSocket. Streaming {len(self.symbols)} symbols.")
                    
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            
                            # Handle combined stream format
                            if "stream" in data:
                                stream = data["stream"]
                                payload = data["data"]
                            else:
                                payload = data
                            
                            # Parse kline data
                            if "e" in payload and payload["e"] == "kline":
                                k = payload["k"]
                                
                                # Only yield finalized bars (kline is closed)
                                if k["x"]:  # x = is_final
                                    bar = Bar(
                                        symbol=k["s"].upper(),  # Normalize to uppercase
                                        interval="1m",
                                        ts=int(k["t"]) // 1000,  # Convert ms to seconds
                                        open=float(k["o"]),
                                        high=float(k["h"]),
                                        low=float(k["l"]),
                                        close=float(k["c"]),
                                        volume=float(k["v"]),
                                    )
                                    yield bar
                        
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse Binance message: {e}")
                        except KeyError as e:
                            logger.warning(f"Unexpected message format from Binance: {e}")
                        except Exception as e:
                            logger.error(f"Error processing Binance message: {e}", exc_info=True)
            
            except (
                websockets.exceptions.WebSocketException,
                asyncio.TimeoutError,
                OSError,
            ) as e:
                self.consecutive_handshake_failures += 1
                logger.error(
                    f"Binance WebSocket connection error (attempt {self.consecutive_handshake_failures}): {e}"
                )
                
                # If fail_fast mode and 3 consecutive handshake failures, give up
                if self.fail_fast and self.consecutive_handshake_failures >= 3:
                    logger.error(
                        "Binance WebSocket unavailable after 3 consecutive connection failures. "
                        "Network may be blocking WebSocket connections."
                    )
                    raise BinanceWsUnavailable(
                        "WebSocket connection failed 3 times - possibly blocked by firewall/network"
                    )
            
            except Exception as e:
                logger.error(f"Unexpected error in Binance stream: {e}", exc_info=True)
            
            finally:
                self._ws = None
            
            # Exponential backoff with jitter
            retry_count += 1
            delay = min(2 ** retry_count + random.uniform(0, 1), max_retry_delay)
            logger.info(f"Reconnecting to Binance WebSocket in {delay:.1f}s (attempt {retry_count})...")
            await asyncio.sleep(delay)
