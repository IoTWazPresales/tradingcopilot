"""Binance streaming adapter (placeholder).

Replace with a real WebSocket client in Cursor.
The rest of the stack is provider-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Iterable


@dataclass
class Kline:
    symbol: str
    interval: str
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float


async def stream_klines(symbols: Iterable[str], interval: str = "1m") -> AsyncIterator[Kline]:
    """Placeholder async generator that yields no data."""
    if False:
        yield  # pragma: no cover
    return
