#!/usr/bin/env python3
"""
Quick sanity check script to verify bars are being written to the database.

Usage:
    python verify_streaming.py

This script:
1. Checks if the database exists
2. Queries bar counts per symbol/interval
3. Shows the most recent bars
4. Verifies timestamps are advancing (live streaming is working)
"""

import sys
import time
from pathlib import Path

try:
    import aiosqlite
    import asyncio
except ImportError:
    print("Error: aiosqlite not installed. Run: pip install aiosqlite")
    sys.exit(1)


async def verify_database(db_path: str = "data/market.db"):
    """Verify the database and show recent bars."""
    
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"❌ Database not found at: {db_path}")
        print("   → Make sure the core API has been started at least once.")
        return False
    
    print(f"✅ Database exists: {db_path}\n")
    
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        
        # Check if bars table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bars'"
        )
        table = await cursor.fetchone()
        if not table:
            print("❌ 'bars' table not found. Database may be corrupted.")
            return False
        
        print("✅ 'bars' table exists\n")
        
        # Count bars by symbol and interval
        cursor = await db.execute("""
            SELECT symbol, interval, COUNT(*) as count
            FROM bars
            GROUP BY symbol, interval
            ORDER BY symbol, interval
        """)
        rows = await cursor.fetchall()
        
        if not rows:
            print("⚠️  No bars in database yet.")
            print("   → Wait 2-3 minutes after starting the core API for bars to accumulate.")
            print("   → Check that providers are configured in .env")
            return False
        
        print("📊 Bar counts by symbol/interval:")
        print("-" * 60)
        print(f"{'Symbol':<15} {'Interval':<10} {'Count':>10}")
        print("-" * 60)
        
        for row in rows:
            print(f"{row['symbol']:<15} {row['interval']:<10} {row['count']:>10,}")
        
        print("-" * 60)
        print()
        
        # Show most recent bars (last 5)
        cursor = await db.execute("""
            SELECT symbol, interval, ts, open, high, low, close, volume
            FROM bars
            ORDER BY ts DESC
            LIMIT 10
        """)
        recent_bars = await cursor.fetchall()
        
        if recent_bars:
            print("🕐 Most recent bars (last 10):")
            print("-" * 100)
            print(f"{'Symbol':<15} {'Interval':<10} {'Timestamp':<20} {'Open':>10} {'Close':>10} {'Volume':>12}")
            print("-" * 100)
            
            for bar in recent_bars:
                ts_str = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(bar['ts']))
                print(
                    f"{bar['symbol']:<15} {bar['interval']:<10} {ts_str:<20} "
                    f"{bar['open']:>10.5f} {bar['close']:>10.5f} {bar['volume']:>12.2f}"
                )
            print("-" * 100)
            print()
        
        # Check if timestamps are recent (within last 5 minutes)
        if recent_bars:
            latest_ts = recent_bars[0]['ts']
            now = int(time.time())
            age_seconds = now - latest_ts
            age_minutes = age_seconds / 60.0
            
            print(f"⏱️  Latest bar timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(latest_ts))}")
            print(f"   Current time:        {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(now))}")
            print(f"   Age: {age_minutes:.1f} minutes ({age_seconds} seconds)\n")
            
            if age_minutes < 5:
                print("✅ Streaming is ACTIVE! Bars are recent (< 5 minutes old)")
            elif age_minutes < 60:
                print(f"⚠️  Streaming may be stalled. Latest bar is {age_minutes:.1f} minutes old.")
                print("   → Check core API logs for errors")
            else:
                print(f"❌ Streaming appears STOPPED. Latest bar is {age_minutes/60:.1f} hours old.")
                print("   → Restart the core API to resume streaming")
            
            return True
        
        return True


async def main():
    """Main entry point."""
    print("=" * 60)
    print("Trading Copilot - Streaming Verification")
    print("=" * 60)
    print()
    
    success = await verify_database()
    
    print()
    print("=" * 60)
    
    if success:
        print("✅ Verification complete!")
    else:
        print("⚠️  Issues found. See messages above.")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

