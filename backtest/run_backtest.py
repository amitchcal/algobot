"""
Backtest runner: pulls historical OHLCV from the Kite sandbox, runs the
Hilega Milega strategy over it, and prints a trade log + P&L summary.

Usage:
    python run_backtest.py --symbol RELIANCE --token 738561 \
        --from 2025-07-01 --to 2026-10-01 --interval 15minute --qty 1

Instrument tokens are looked up via KiteAdapter.instruments("NSE") if you
don't already know one - see fetch_instrument_token() below.
"""

import argparse
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from broker.kite_adapter import KiteAdapter, BrokerConfig
from engine.strategy import HilegaMilegaStrategy, TSLConfig


def fetch_instrument_token(adapter: KiteAdapter, tradingsymbol: str, exchange="NSE"):
    instruments = adapter.instruments(exchange)
    for row in instruments:
        if row["tradingsymbol"] == tradingsymbol:
            return row["instrument_token"]
    raise ValueError(f"Instrument {tradingsymbol} not found on {exchange}")


def summarize(trades):
    if not trades:
        print("No trades generated.")
        return
    rows = [{
        "symbol": t.symbol,
        "direction": t.direction.name,
        "entry_time": t.entry_time,
        "entry_price": round(t.entry_price, 2),
        "exit_time": t.exit_time,
        "exit_price": round(t.exit_price, 2) if t.exit_price else None,
        "exit_reason": t.exit_reason.value if t.exit_reason else None,
        "pnl": round(t.pnl(), 2),
        "pnl_pct": round(t.pnl_pct(), 2),
    } for t in trades]
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))

    total_pnl = df["pnl"].sum()
    win_rate = (df["pnl"] > 0).mean() * 100
    print(f"\nTrades: {len(df)}  |  Win rate: {win_rate:.1f}%  |  Total P&L: {total_pnl:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--exchange", default="NSE")
    ap.add_argument("--from", dest="from_date", required=True)
    ap.add_argument("--to", dest="to_date", required=True)
    ap.add_argument("--interval", default="15minute",
                     choices=["minute", "15minute", "day"])
    ap.add_argument("--qty", type=int, default=1)
    ap.add_argument("--tsl-mode", default="percent", choices=["percent", "points"])
    ap.add_argument("--tsl-value", type=float, default=1.0)
    ap.add_argument("--tsl-activate-after", type=float, default=0.0)
    ap.add_argument("--api-key", default=os.environ.get("KITE_API_KEY", "sandboxdemo"))
    ap.add_argument("--access-token", default=os.environ.get("KITE_ACCESS_TOKEN", ""))
    args = ap.parse_args()

    cfg = BrokerConfig(api_key=args.api_key, access_token=args.access_token, paper_mode=True)
    adapter = KiteAdapter(cfg)

    token = fetch_instrument_token(adapter, args.symbol, args.exchange)
    ohlcv = adapter.historical_data(token, args.from_date, args.to_date, args.interval)

    tsl_cfg = TSLConfig(mode=args.tsl_mode, trail_value=args.tsl_value,
                         activate_after=args.tsl_activate_after)
    squareoff = "15:15" if args.interval != "day" else None
    strat = HilegaMilegaStrategy(args.symbol, args.qty, tsl_cfg,
                                  intraday_squareoff_time=squareoff)
    strat.run(ohlcv)

    summarize(strat.closed_trades)


if __name__ == "__main__":
    main()
