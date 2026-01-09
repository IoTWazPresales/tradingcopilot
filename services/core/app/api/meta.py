"""
Metadata API endpoints for UI support.

Provides information about available instruments, intervals, and data readiness.
"""

from fastapi import APIRouter, Query, Depends
from typing import Dict, List, Any
import logging

from ..storage.sqlite import SQLiteStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/meta", tags=["metadata"])

# Store instance (set by main.py)
_store: SQLiteStore | None = None


def set_store(store: SQLiteStore):
    """Set the store instance."""
    global _store
    _store = store


def get_store() -> SQLiteStore:
    """Get the store instance."""
    if _store is None:
        raise RuntimeError("Store not initialized")
    return _store


@router.get("/instruments")
async def get_instruments(
    min_bars_1m: int = Query(50, ge=0, description="Minimum 1m bars required to include symbol"),
    store: SQLiteStore = Depends(get_store)
) -> Dict[str, Any]:
    """
    Get available instruments with data readiness information.
    
    Returns:
        - symbols: List of symbols that have sufficient 1m bar data
        - intervals: List of distinct intervals present in the database
        - counts: Per-symbol per-interval bar counts (for common intervals)
    
    Example:
        {
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "intervals": ["1m", "5m", "15m", "1h", "4h", "1d"],
            "counts": {
                "BTCUSDT": {"1m": 5000, "5m": 1000, "15m": 333, ...},
                "ETHUSDT": {"1m": 5000, "5m": 1000, "15m": 333, ...}
            }
        }
    """
    try:
        # Get all distinct symbols with 1m data
        all_symbols = await store.get_distinct_symbols(interval="1m")
        
        # Filter by minimum bar count
        symbols_with_counts = []
        for symbol in all_symbols:
            bars = await store.fetch_bars(symbol, "1m", limit=min_bars_1m + 1)
            if len(bars) >= min_bars_1m:
                symbols_with_counts.append(symbol)
        
        if not symbols_with_counts:
            return {
                "symbols": [],
                "intervals": [],
                "counts": {}
            }
        
        # Get all distinct intervals
        all_intervals = await store.get_distinct_intervals()
        
        # Common intervals to report (in order)
        common_intervals = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
        intervals = [i for i in common_intervals if i in all_intervals]
        
        # Get counts per symbol per interval
        counts = {}
        for symbol in symbols_with_counts:
            counts[symbol] = {}
            for interval in intervals:
                bars = await store.fetch_bars(symbol, interval, limit=100000)
                counts[symbol][interval] = len(bars)
        
        return {
            "symbols": sorted(symbols_with_counts),
            "intervals": intervals,
            "counts": counts
        }
    
    except Exception as e:
        logger.error(f"Error fetching instruments: {e}", exc_info=True)
        return {
            "symbols": [],
            "intervals": [],
            "counts": {},
            "error": str(e)
        }
