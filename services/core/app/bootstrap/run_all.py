"""
One-command bootstrap launcher for Trading Copilot.

Starts backend API + Streamlit UI with automatic backfill if needed.

Usage:
    python -m app.bootstrap.run_all
    python -m app.bootstrap.run_all --symbol ETHUSDT --days 3 --prefer_rest
    python -m app.bootstrap.run_all --skip_backfill --no_browser
"""

import argparse
import asyncio
import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# Ensure app is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.storage.sqlite import SQLiteStore
from app.backtest.binance_history import backfill_to_store


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Trading Copilot - One Command Bootstrap",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m app.bootstrap.run_all
  python -m app.bootstrap.run_all --symbol ETHUSDT --days 3
  python -m app.bootstrap.run_all --skip_backfill --prefer_rest
  python -m app.bootstrap.run_all --min_1m_bars 5000 --days 14
        """
    )
    
    # Database
    parser.add_argument(
        "--db",
        default="data/market.db",
        help="SQLite database path (default: data/market.db)"
    )
    
    # Backfill settings
    parser.add_argument(
        "--symbols",
        default="BTCUSDT,ETHUSDT",
        help="Comma-separated symbols to backfill (default: BTCUSDT,ETHUSDT)"
    )
    parser.add_argument(
        "--intervals",
        default="1m,5m,15m,1h,4h,1d,1w",
        help="Comma-separated intervals to ensure (default: 1m,5m,15m,1h,4h,1d,1w)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days to backfill (default: 30)"
    )
    parser.add_argument(
        "--min_bars",
        type=str,
        default="1m:5000,5m:2000,15m:1000,1h:400,4h:200,1d:60,1w:30",
        help="Minimum bars per interval (format: interval:count,interval:count)"
    )
    parser.add_argument(
        "--skip_backfill",
        action="store_true",
        help="Skip automatic backfill check"
    )
    
    # Server ports
    parser.add_argument(
        "--api_port",
        type=int,
        default=8080,
        help="FastAPI port (default: 8080)"
    )
    parser.add_argument(
        "--ui_port",
        type=int,
        default=8501,
        help="Streamlit port (default: 8501)"
    )
    
    # Behavior
    parser.add_argument(
        "--no_browser",
        action="store_true",
        help="Don't open browser automatically"
    )
    parser.add_argument(
        "--prefer_rest",
        action="store_true",
        help="Force Binance REST mode (avoids WebSocket failures)"
    )
    
    return parser.parse_args()


async def check_and_backfill(args):
    """
    Check database for sufficient data and backfill if needed.
    
    For all symbols and intervals specified, checks if minimum bar counts
    are met. If not, backfills 1m data and aggregates to higher timeframes.
    
    Returns:
        bool: True if any backfill was performed
    """
    if args.skip_backfill:
        print("⏩ Skipping backfill (--skip_backfill)")
        return False
    
    db_path = Path(args.db)
    
    # Ensure db directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize store
    store = SQLiteStore(str(db_path))
    await store.init()
    
    # Parse symbols and intervals
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    intervals = [i.strip() for i in args.intervals.split(",") if i.strip()]
    
    # Parse min_bars mapping (interval:count,interval:count)
    min_bars_map = {}
    for pair in args.min_bars.split(","):
        if ":" in pair:
            interval, count = pair.split(":")
            min_bars_map[interval.strip()] = int(count.strip())
    
    print(f"📊 Checking data for {len(symbols)} symbol(s) across {len(intervals)} interval(s)...")
    print()
    
    any_backfill_needed = False
    
    for symbol in symbols:
        print(f"Checking {symbol}:")
        
        # Check 1m bars first (required for aggregation)
        try:
            bars_1m = await store.fetch_bars(symbol, "1m", limit=100000)
            count_1m = len(bars_1m)
            min_1m = min_bars_map.get("1m", 5000)
            print(f"  1m: {count_1m} bars (need {min_1m})")
            
            if count_1m < min_1m:
                any_backfill_needed = True
        except Exception as e:
            print(f"  1m: Error checking - {e}")
            any_backfill_needed = True
    
    if not any_backfill_needed:
        print("\n✓ All symbols have sufficient 1m data. Checking higher timeframes...")
        
        # Check higher timeframes
        for symbol in symbols:
            for interval in intervals:
                if interval == "1m":
                    continue
                
                try:
                    bars = await store.fetch_bars(symbol, interval, limit=100000)
                    count = len(bars)
                    min_count = min_bars_map.get(interval, 100)
                    
                    if count < min_count:
                        print(f"  {symbol} {interval}: {count} bars (need {min_count}) - will aggregate")
                        any_backfill_needed = True
                except Exception:
                    any_backfill_needed = True
    
    if not any_backfill_needed:
        print("\n✓ All intervals have sufficient data. Skipping backfill.")
        return False
    
    # Perform backfill
    print(f"\n🔄 Starting backfill for {len(symbols)} symbol(s)...")
    print(f"   Days: {args.days}")
    print()
    
    try:
        from datetime import datetime, timedelta
        from app.backtest.binance_history import aggregate_to_higher_timeframes
        
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=args.days)
        
        total_inserted = 0
        
        for symbol in symbols:
            print(f"\n📥 Backfilling {symbol}...")
            
            # Backfill 1m bars
            inserted_1m = await backfill_to_store(
                store=store,
                symbol=symbol,
                interval="1m",
                start_dt=start_dt,
                end_dt=end_dt,
                progress=True,
                progress_cb=lambda msg: print(f"  {msg}")
            )
            
            total_inserted += inserted_1m
            
            # Aggregate to higher timeframes
            higher_intervals = [i for i in intervals if i != "1m"]
            if higher_intervals:
                print(f"\n📊 Aggregating {symbol} to higher timeframes...")
                inserted_higher = await aggregate_to_higher_timeframes(
                    store=store,
                    symbol=symbol,
                    source_interval="1m",
                    target_intervals=higher_intervals,
                    progress=True,
                    progress_cb=lambda msg: print(f"  {msg}")
                )
                total_inserted += inserted_higher
        
        print(f"\n✅ Backfill complete: {total_inserted} total bars across all symbols/intervals")
        return True
    
    except Exception as e:
        print(f"\n✗ Backfill failed: {e}")
        import traceback
        traceback.print_exc()
        print("   Continuing anyway (live streaming will populate data)...")
        return False


def start_backend(api_port: int, prefer_rest: bool):
    """
    Start FastAPI backend as subprocess.
    
    Returns:
        subprocess.Popen: Backend process
    """
    print(f"\n🚀 Starting backend API on port {api_port}...")
    
    # Set environment for REST preference
    env = os.environ.copy()
    if prefer_rest:
        env["BINANCE_TRANSPORT"] = "rest"
        print("   ⚙️  Using Binance REST mode (prefer_rest=True)")
    else:
        env["BINANCE_TRANSPORT"] = "auto"
        print("   ⚙️  Using Binance AUTO mode (WS → REST fallback)")
    
    # Start uvicorn
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(api_port),
    ]
    
    # Use CREATE_NEW_PROCESS_GROUP on Windows for clean shutdown
    kwargs = {
        "env": env,
        "cwd": str(Path(__file__).parent.parent.parent),
    }
    
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    
    process = subprocess.Popen(cmd, **kwargs)
    
    print(f"   PID: {process.pid}")
    return process


def start_ui(api_port: int, ui_port: int):
    """
    Start Streamlit UI as subprocess.
    
    Returns:
        subprocess.Popen: UI process
    """
    print(f"\n🖥️  Starting Streamlit UI on port {ui_port}...")
    
    # Set API base URL for UI
    env = os.environ.copy()
    env["API_BASE"] = f"http://localhost:{api_port}"
    
    # Start streamlit
    ui_file = Path(__file__).parent.parent / "ui" / "streamlit_app.py"
    
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(ui_file),
        "--server.port",
        str(ui_port),
        "--server.headless",
        "true",
    ]
    
    # Use CREATE_NEW_PROCESS_GROUP on Windows
    kwargs = {"env": env}
    
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    
    process = subprocess.Popen(cmd, **kwargs)
    
    print(f"   PID: {process.pid}")
    return process


def wait_for_backend(api_port: int, max_retries: int = 20, delay: float = 1.0) -> bool:
    """
    Wait for backend to be ready.
    
    Returns:
        bool: True if backend is ready, False if timeout
    """
    print(f"\n⏳ Waiting for backend to be ready...")
    
    import urllib.request
    import urllib.error
    
    for i in range(max_retries):
        try:
            url = f"http://localhost:{api_port}/health"
            response = urllib.request.urlopen(url, timeout=2)
            if response.status == 200:
                print(f"✓ Backend ready after {i + 1} attempts")
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, Exception):
            pass
        
        if i < max_retries - 1:
            time.sleep(delay)
    
    print(f"✗ Backend not ready after {max_retries} attempts")
    return False


def wait_for_ui(ui_port: int, max_retries: int = 15, delay: float = 1.0) -> bool:
    """
    Wait for Streamlit UI to be ready.
    
    Returns:
        bool: True if UI is ready, False if timeout
    """
    print(f"\n⏳ Waiting for UI to be ready...")
    
    import urllib.request
    import urllib.error
    
    for i in range(max_retries):
        try:
            url = f"http://localhost:{ui_port}"
            response = urllib.request.urlopen(url, timeout=2)
            if response.status == 200:
                print(f"✓ UI ready after {i + 1} attempts")
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, Exception):
            pass
        
        if i < max_retries - 1:
            time.sleep(delay)
    
    print(f"✗ UI not ready after {max_retries} attempts")
    return False


def cleanup_processes(backend_process, ui_process):
    """Terminate both processes cleanly."""
    print("\n\n🛑 Shutting down...")
    
    # Terminate UI first
    if ui_process and ui_process.poll() is None:
        print("   Stopping UI...")
        try:
            if sys.platform == "win32":
                # Use CTRL_BREAK_EVENT on Windows
                ui_process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                ui_process.terminate()
            ui_process.wait(timeout=5)
        except Exception as e:
            print(f"   Force killing UI: {e}")
            ui_process.kill()
    
    # Terminate backend
    if backend_process and backend_process.poll() is None:
        print("   Stopping backend...")
        try:
            if sys.platform == "win32":
                backend_process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                backend_process.terminate()
            backend_process.wait(timeout=5)
        except Exception as e:
            print(f"   Force killing backend: {e}")
            backend_process.kill()
    
    print("✓ Shutdown complete")


def main():
    """Main bootstrap entry point."""
    args = parse_args()
    
    print("=" * 60)
    print("🚀 TRADING COPILOT - ONE COMMAND BOOTSTRAP")
    print("=" * 60)
    print()
    
    # Check if streamlit is installed
    try:
        import streamlit
    except ImportError:
        print("✗ Streamlit is not installed.")
        print()
        print("Please install dependencies:")
        print("  pip install -r requirements.txt")
        print()
        return 1
    
    backend_process = None
    ui_process = None
    
    try:
        # Step 1: Check and backfill
        asyncio.run(check_and_backfill(args))
        
        # Step 2: Start backend
        backend_process = start_backend(args.api_port, args.prefer_rest)
        
        # Step 3: Wait for backend
        if not wait_for_backend(args.api_port):
            print("\n✗ Backend failed to start. Check logs above.")
            return 1
        
        # Step 4: Start UI
        ui_process = start_ui(args.api_port, args.ui_port)
        
        # Step 5: Wait for UI
        if not wait_for_ui(args.ui_port):
            print("\n⚠️  UI may not be ready, but continuing...")
        
        # Step 6: Open browser
        ui_url = f"http://localhost:{args.ui_port}"
        if not args.no_browser:
            print(f"\n🌐 Opening browser: {ui_url}")
            try:
                webbrowser.open(ui_url)
            except Exception as e:
                print(f"   Could not open browser: {e}")
        
        # Step 7: Success message
        print("\n" + "=" * 60)
        print("✅ TRADING COPILOT IS RUNNING")
        print("=" * 60)
        print(f"\n🔗 UI:      {ui_url}")
        print(f"🔗 API:     http://localhost:{args.api_port}")
        print(f"🔗 Docs:    http://localhost:{args.api_port}/docs")
        print("\n⌨️  Press CTRL+C to stop")
        print("=" * 60)
        print()
        
        # Step 8: Wait for Ctrl+C
        while True:
            time.sleep(1)
            
            # Check if processes died
            if backend_process.poll() is not None:
                print("\n✗ Backend process died unexpectedly")
                break
            
            if ui_process.poll() is not None:
                print("\n✗ UI process died unexpectedly")
                break
    
    except KeyboardInterrupt:
        print("\n\n⌨️  Received Ctrl+C")
    
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        cleanup_processes(backend_process, ui_process)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
