"""Streaming runner that orchestrates provider streams and aggregation."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from ..config import Settings
from ..providers.base import Bar
from ..providers.binance_ws import BinanceWebSocketStreamer, BinanceWsUnavailable
from ..providers.binance_rest import BinanceRESTPoller
from ..providers.oanda_stream import OandaStreamingClient
from ..storage.sqlite import SQLiteStore
from .aggregator import BarAggregator


logger = logging.getLogger(__name__)


class StreamingRunner:
    """
    Manages lifecycle of provider streams and aggregation.
    
    Starts enabled providers, consumes their bars, and feeds to aggregator.
    """
    
    def __init__(self, settings: Settings, store: SQLiteStore):
        self.settings = settings
        self.store = store
        self.aggregator = BarAggregator(store, settings.get_bar_intervals())
        self.tasks: list[asyncio.Task] = []
        self.active_binance_transport: str | None = None  # Track which transport is active
        
    async def start(self) -> None:
        """Start all enabled provider streams."""
        logger.info("Starting streaming runner...")
        
        # Initialize storage
        await self.store.init()
        
        enabled_providers = self.settings.get_enabled_providers()
        logger.info(f"Enabled providers: {enabled_providers}")
        
        # Start Binance if enabled
        if "binance" in enabled_providers:
            await self._start_binance()
        
        # Start OANDA if enabled
        if "oanda" in enabled_providers:
            await self._start_oanda()
        
        if not self.tasks:
            logger.warning("No provider tasks started. Check your configuration.")
        else:
            logger.info(f"Started {len(self.tasks)} provider task(s).")
    
    async def stop(self) -> None:
        """Stop all provider streams gracefully."""
        logger.info("Stopping streaming runner...")
        
        for task in self.tasks:
            task.cancel()
        
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        logger.info("Streaming runner stopped.")
    
    async def _start_binance(self) -> None:
        """
        Start Binance stream with transport mode selection.
        
        Modes:
        - "ws": WebSocket only (fail if unavailable)
        - "rest": REST polling only
        - "auto": Try WebSocket first, fallback to REST if unavailable
        """
        symbols = self.settings.get_binance_symbols()
        
        if not symbols:
            logger.warning("Binance enabled but no symbols configured. Skipping Binance.")
            return
        
        transport = self.settings.binance_transport.lower()
        
        if transport == "ws":
            # WebSocket only - fail loudly if unavailable
            logger.info(f"Starting Binance WebSocket (mode: ws) for symbols: {symbols}")
            await self._start_binance_ws(symbols, fail_fast=False)
        
        elif transport == "rest":
            # REST only
            logger.info(f"Starting Binance REST poller (mode: rest) for symbols: {symbols}")
            await self._start_binance_rest(symbols)
        
        elif transport == "auto":
            # Try WebSocket first, fallback to REST if unavailable
            logger.info(f"Starting Binance (mode: auto) for symbols: {symbols}")
            try:
                await self._start_binance_ws(symbols, fail_fast=True)
            except BinanceWsUnavailable:
                logger.warning(
                    "Binance WebSocket unavailable. Falling back to REST polling mode. "
                    "Set binance_transport=rest in .env to skip WebSocket attempts."
                )
                await self._start_binance_rest(symbols)
        
        else:
            logger.error(
                f"Invalid binance_transport: '{transport}'. Must be 'ws', 'rest', or 'auto'. "
                "Defaulting to 'auto'."
            )
            await self._start_binance()  # Recursive call with default
    
    async def _start_binance_ws(self, symbols: list[str], fail_fast: bool = False) -> None:
        """Start Binance WebSocket stream."""
        streamer = BinanceWebSocketStreamer(symbols, fail_fast=fail_fast)
        self.active_binance_transport = "ws"
        task = asyncio.create_task(self._consume_stream(streamer.stream_bars(), "Binance-WS"))
        self.tasks.append(task)
    
    async def _start_binance_rest(self, symbols: list[str]) -> None:
        """Start Binance REST polling."""
        poller = BinanceRESTPoller(symbols, self.settings.binance_rest_poll_seconds)
        self.active_binance_transport = "rest"
        task = asyncio.create_task(self._consume_stream(poller.stream_bars(), "Binance-REST"))
        self.tasks.append(task)
    
    async def _start_oanda(self) -> None:
        """Start OANDA pricing stream."""
        api_key = self.settings.oanda_api_key
        account_id = self.settings.oanda_account_id
        instruments = self.settings.get_oanda_instruments()
        
        if not api_key or not account_id:
            logger.warning(
                "OANDA enabled but missing credentials (oanda_api_key or oanda_account_id). "
                "Skipping OANDA stream."
            )
            return
        
        if not instruments:
            logger.warning("OANDA enabled but no instruments configured. Skipping OANDA.")
            return
        
        logger.info(f"Starting OANDA stream with instruments: {instruments}")
        streamer = OandaStreamingClient(
            instruments=instruments,
            api_key=api_key,
            account_id=account_id,
            environment=self.settings.oanda_environment,
        )
        task = asyncio.create_task(self._consume_stream(streamer.stream_bars(), "OANDA"))
        self.tasks.append(task)
    
    async def _consume_stream(self, stream: AsyncIterator[Bar], provider_name: str) -> None:
        """
        Consume bars from a provider stream and feed to aggregator.
        
        Args:
            stream: Async iterator yielding Bar objects
            provider_name: Name of the provider (for logging)
        """
        try:
            async for bar in stream:
                # Aggregator now handles logging (throttled to once per minute per symbol)
                await self.aggregator.process_bar(bar)
        except asyncio.CancelledError:
            logger.info(f"{provider_name} stream cancelled.")
            raise
        except Exception as e:
            logger.error(f"Fatal error in {provider_name} consumer: {e}", exc_info=True)

