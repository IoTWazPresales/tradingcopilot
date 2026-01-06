"""Base types and protocols for market data providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol


@dataclass
class Bar:
    """Unified OHLCV bar representation."""
    symbol: str
    interval: str
    ts: int  # Unix timestamp in seconds (start of the bar)
    open: float
    high: float
    low: float
    close: float
    volume: float


class StreamProvider(Protocol):
    """Protocol for streaming market data providers."""
    
    async def stream_bars(self) -> AsyncIterator[Bar]:
        """
        Async generator that yields Bar objects.
        
        Should handle reconnection internally and never raise unhandled exceptions.
        If the provider encounters a fatal error, it should log and stop gracefully.
        """
        ...

