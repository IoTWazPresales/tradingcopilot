import os
import aiosqlite
from dataclasses import dataclass
from typing import Any, Iterable, Optional


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS bars (
  symbol TEXT NOT NULL,
  interval TEXT NOT NULL,
  ts INTEGER NOT NULL,
  open REAL NOT NULL,
  high REAL NOT NULL,
  low REAL NOT NULL,
  close REAL NOT NULL,
  volume REAL NOT NULL,
  PRIMARY KEY(symbol, interval, ts)
);
"""


@dataclass
class BarRow:
  symbol: str
  interval: str
  ts: int
  open: float
  high: float
  low: float
  close: float
  volume: float


class SQLiteStore:
  def __init__(self, path: str):
    self.path = path

  async def init(self) -> None:
    os.makedirs(os.path.dirname(self.path), exist_ok=True)
    async with aiosqlite.connect(self.path) as db:
      await db.execute(CREATE_SQL)
      await db.commit()

  async def upsert_bars(self, bars: Iterable[BarRow]) -> int:
    bars_list = list(bars)
    if not bars_list:
      return 0
    async with aiosqlite.connect(self.path) as db:
      await db.executemany(
        """
        INSERT INTO bars (symbol, interval, ts, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, interval, ts) DO UPDATE SET
          open=excluded.open,
          high=excluded.high,
          low=excluded.low,
          close=excluded.close,
          volume=excluded.volume;
        """,
        [(b.symbol, b.interval, b.ts, b.open, b.high, b.low, b.close, b.volume) for b in bars_list],
      )
      await db.commit()
    return len(bars_list)

  async def fetch_bars(
    self,
    symbol: str,
    interval: str,
    limit: int = 500,
  ) -> list[dict[str, Any]]:
    async with aiosqlite.connect(self.path) as db:
      db.row_factory = aiosqlite.Row
      cur = await db.execute(
        """
        SELECT symbol, interval, ts, open, high, low, close, volume
        FROM bars
        WHERE symbol=? AND interval=?
        ORDER BY ts DESC
        LIMIT ?;
        """,
        (symbol, interval, limit),
      )
      rows = await cur.fetchall()
      return [dict(r) for r in reversed(rows)]
  
  async def get_distinct_symbols(self, interval: Optional[str] = None) -> list[str]:
    """
    Get distinct symbols from the database.
    
    Args:
        interval: Optional interval filter
        
    Returns:
        List of unique symbols
    """
    async with aiosqlite.connect(self.path) as db:
      if interval:
        cur = await db.execute(
          "SELECT DISTINCT symbol FROM bars WHERE interval=? ORDER BY symbol",
          (interval,)
        )
      else:
        cur = await db.execute(
          "SELECT DISTINCT symbol FROM bars ORDER BY symbol"
        )
      rows = await cur.fetchall()
      return [row[0] for row in rows]
  
  async def get_distinct_intervals(self) -> list[str]:
    """
    Get distinct intervals from the database.
    
    Returns:
        List of unique intervals
    """
    async with aiosqlite.connect(self.path) as db:
      cur = await db.execute(
        "SELECT DISTINCT interval FROM bars ORDER BY interval"
      )
      rows = await cur.fetchall()
      return [row[0] for row in rows]