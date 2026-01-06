from __future__ import annotations

import logging
import math
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .config import get_settings
from .storage.sqlite import SQLiteStore
from .streaming.runner import StreamingRunner


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

settings = get_settings()
store = SQLiteStore(settings.sqlite_path)
runner: StreamingRunner | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup/shutdown."""
    global runner
    
    # Startup: initialize storage and start streaming
    await store.init()
    runner = StreamingRunner(settings, store)
    await runner.start()
    
    yield
    
    # Shutdown: stop streaming gracefully
    if runner:
        await runner.stop()


app = FastAPI(
    title="Trading Copilot Core API",
    version="0.1.0",
    lifespan=lifespan,
)


class BarQuery(BaseModel):
    symbol: str
    interval: str = "1h"
    limit: int = Field(default=300, ge=10, le=5000)


class ForecastRequest(BaseModel):
    symbol: str
    interval: str = "1h"
    horizon: str = "hours"  # minutes|hours|days|weeks
    lookback: int = Field(default=300, ge=50, le=5000)


class ForecastResponse(BaseModel):
    symbol: str
    interval: str
    horizon: str
    asof_ts: int
    probs: dict[str, float]
    buy_zone: tuple[float, float] | None
    sell_zone: tuple[float, float] | None
    invalidation: float | None
    confidence: float
    notes: list[str]


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "ts": int(time.time()), "provider": settings.provider}


@app.get("/v1/providers")
async def get_providers() -> dict[str, Any]:
    """Get information about enabled providers and their configuration."""
    return {
        "enabled": settings.get_enabled_providers(),
        "binance": {
            "transport": settings.binance_transport,
            "active_transport": runner.active_binance_transport if runner else None,
            "symbols": settings.get_binance_symbols(),
            "rest_poll_seconds": settings.binance_rest_poll_seconds,
        },
        "oanda": {
            "configured": bool(settings.oanda_api_key and settings.oanda_account_id),
            "instruments": settings.get_oanda_instruments() if settings.oanda_api_key else [],
            "environment": settings.oanda_environment,
        },
    }


@app.get("/v1/bars")
async def get_bars(symbol: str, interval: str = "1h", limit: int = 300) -> list[dict[str, Any]]:
    return await store.fetch_bars(symbol=symbol, interval=interval, limit=limit)


@app.post("/v1/forecast", response_model=ForecastResponse)
async def forecast(req: ForecastRequest) -> ForecastResponse:
    """Baseline forecast.

    This intentionally starts as a *calibrated statistical baseline* so it works
    immediately. You will replace/augment this with ML models in Cursor.
    """
    bars = await store.fetch_bars(symbol=req.symbol, interval=req.interval, limit=req.lookback)
    if len(bars) < 60:
        return ForecastResponse(
            symbol=req.symbol,
            interval=req.interval,
            horizon=req.horizon,
            asof_ts=int(time.time()),
            probs={"up": 0.34, "flat": 0.33, "down": 0.33},
            buy_zone=None,
            sell_zone=None,
            invalidation=None,
            confidence=0.1,
            notes=["Not enough stored bars yet. Start a provider stream and let it run."],
        )

    closes = [float(b["close"]) for b in bars]
    last = closes[-1]

    # Simple momentum + volatility proxy baseline
    r = [(closes[i] - closes[i - 1]) / max(1e-9, closes[i - 1]) for i in range(1, len(closes))]
    mu = sum(r[-50:]) / 50.0
    var = sum((x - mu) ** 2 for x in r[-50:]) / 49.0
    sigma = math.sqrt(max(1e-12, var))

    z = mu / max(1e-9, sigma)
    up = 1.0 / (1.0 + math.exp(-2.0 * z))
    down = 1.0 - up
    flat = max(0.0, 0.25 - min(0.2, abs(z) * 0.05))

    # Normalize
    s = up + down + flat
    up, down, flat = up / s, down / s, flat / s

    # Trade zones: mean-reversion entry around last minus/plus volatility band
    band = last * (sigma * 2.0)
    buy_zone = (last - 0.6 * band, last - 0.2 * band) if up > 0.52 else None
    sell_zone = (last + 0.2 * band, last + 0.8 * band) if up > 0.52 else None
    invalidation = last - 1.2 * band if up > 0.52 else None

    confidence = min(0.85, 0.35 + abs(z) * 0.12)

    notes = [
        "Baseline model: momentum/volatility proxy. Replace with ML ensemble.",
        f"mu={mu:.6f} sigma={sigma:.6f} z={z:.2f}",
    ]

    return ForecastResponse(
        symbol=req.symbol,
        interval=req.interval,
        horizon=req.horizon,
        asof_ts=int(time.time()),
        probs={"up": float(up), "flat": float(flat), "down": float(down)},
        buy_zone=buy_zone,
        sell_zone=sell_zone,
        invalidation=invalidation,
        confidence=float(confidence),
        notes=notes,
    )
