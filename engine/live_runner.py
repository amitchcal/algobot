"""
Live PAPER TRADING runner — equity bots only (intraday_stock,
carry_forward_swing_stock), against each bot's manual `watchlist`.

Options/futures/commodity bots are NOT handled here yet (strike/expiry/
contract resolution isn't built) — those bot types are skipped with a
warning if active.

What this script does, every poll:
    1. Re-reads config/bots.yaml and config/secrets.yaml (so dashboard
       changes take effect without restarting the process)
    2. For each ACTIVE equity bot inside its trading_window:
        - for each symbol in its watchlist, pulls the latest closed
          candle(s) from the Kite SANDBOX, feeds it through
          HilegaMilegaStrategy.on_bar()
        - on a fresh entry/exit, places a sandbox order via KiteAdapter
          (paper money only — this never touches a live account unless
          bot["paper_mode"] is explicitly False AND a live access_token
          is present)
        - appends the trade to data/trades_<bot_id>.csv for the
          dashboard to display
    3. Sleeps until the next candle boundary and repeats

Run:
    python engine/live_runner.py

Leave this running in a terminal during market hours (09:15-15:30 IST for
equity). Stop with Ctrl+C.
"""

import os
import sys
import time
import csv
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.store import load_bots, load_secrets, BOT_TYPES, ROOT
from broker.kite_adapter import KiteAdapter, BrokerConfig
from engine.strategy import HilegaMilegaStrategy, TSLConfig
from engine.indicators import compute_hilega_milega

DATA_DIR = os.path.join(ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

EQUITY_BOT_TYPES = {"intraday_stock", "carry_forward_swing_stock"}
POLL_SECONDS = 60  # check every minute; candle-close logic below decides
                    # whether there's actually new data to act on


def log_trade(bot_id: str, trade):
    path = os.path.join(DATA_DIR, f"trades_{bot_id}.csv")
    write_header = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["symbol", "direction", "entry_time", "entry_price",
                              "exit_time", "exit_price", "exit_reason", "pnl", "pnl_pct"])
        writer.writerow([
            trade.symbol, trade.direction.name, trade.entry_time, round(trade.entry_price, 2),
            trade.exit_time, round(trade.exit_price, 2) if trade.exit_price else "",
            trade.exit_reason.value if trade.exit_reason else "",
            round(trade.pnl(), 2), round(trade.pnl_pct(), 2),
        ])


def in_trading_window(bot) -> bool:
    now = datetime.now().strftime("%H:%M")
    return bot["trading_window"]["start"] <= now <= bot["trading_window"]["end"]


def get_adapter(bot, secrets_cfg):
    broker_secrets = secrets_cfg.get("brokers", {}).get(bot["broker"], {})
    api_key = broker_secrets.get("api_key") or "sandboxdemo"
    access_token = broker_secrets.get("access_token", "")
    if not access_token:
        print(f"[{bot['id']}] No access token saved yet for {bot['broker']} "
              f"— set it on the Broker Login page. Skipping this bot for now.")
        return None
    cfg = BrokerConfig(api_key=api_key, access_token=access_token,
                        paper_mode=bot["paper_mode"])
    return KiteAdapter(cfg)


# one running HilegaMilegaStrategy instance per (bot_id, symbol), kept across
# polls so open trades persist between iterations
_strategy_cache = {}


def get_strategy(bot, symbol):
    key = (bot["id"], symbol)
    if key not in _strategy_cache:
        tsl_cfg = TSLConfig(mode=bot["tsl"]["mode"],
                             trail_value=bot["tsl"]["trail_value"],
                             activate_after=bot["tsl"]["activate_after"])
        squareoff = bot["trading_window"]["end"] if not BOT_TYPES[bot["bot_type"]]["carry_forward"] else None
        _strategy_cache[key] = HilegaMilegaStrategy(
            symbol=symbol, qty=bot["lot_size"], tsl_config=tsl_cfg,
            intraday_squareoff_time=squareoff,
        )
    return _strategy_cache[key]


def process_bot(bot, secrets_cfg):
    meta = BOT_TYPES[bot["bot_type"]]
    if bot["bot_type"] not in EQUITY_BOT_TYPES:
        print(f"[{bot['id']}] bot_type '{bot['bot_type']}' not yet supported "
              f"by the live runner (needs strike/expiry/contract resolution) — skipping.")
        return
    if not bot.get("watchlist"):
        print(f"[{bot['id']}] no watchlist configured — skipping.")
        return
    if not in_trading_window(bot):
        return

    adapter = get_adapter(bot, secrets_cfg)
    if adapter is None:
        return

    interval = "day" if bot["bot_type"] == "carry_forward_swing_stock" else "5minute"

    for symbol in bot["watchlist"]:
        try:
            token = None
            for row in adapter.instruments(meta["exchange"]):
                if row["tradingsymbol"] == symbol:
                    token = row["instrument_token"]
                    break
            if token is None:
                print(f"[{bot['id']}] symbol {symbol} not found on {meta['exchange']}, skipping.")
                continue

            to_date = datetime.now()
            from_date = to_date - timedelta(days=5 if interval != "day" else 200)
            ohlcv = adapter.historical_data(token, from_date, to_date, interval)
            if ohlcv.empty:
                continue

            enriched = compute_hilega_milega(ohlcv)
            strat = get_strategy(bot, symbol)

            last_ts, last_row = enriched.index[-1], enriched.iloc[-1]
            was_open = strat.open_trade is not None
            strat.on_bar(last_ts, last_row)

            # a trade just closed this bar -> log it, and place the paper exit order
            if was_open and strat.open_trade is None and strat.closed_trades:
                closed = strat.closed_trades[-1]
                log_trade(bot["id"], closed)
                side = "SELL" if closed.direction.name == "LONG" else "BUY"
                adapter.place_order(symbol, meta["exchange"], side, closed.qty,
                                     product=meta["product"], price=closed.exit_price)
                print(f"[{bot['id']}] {symbol} EXIT {closed.direction.name} "
                      f"@ {closed.exit_price} ({closed.exit_reason.value}) pnl={closed.pnl():.2f}")

            # a trade just opened this bar -> place the paper entry order
            if not was_open and strat.open_trade is not None:
                t = strat.open_trade
                side = "BUY" if t.direction.name == "LONG" else "SELL"
                adapter.place_order(symbol, meta["exchange"], side, t.qty,
                                     product=meta["product"], price=t.entry_price)
                print(f"[{bot['id']}] {symbol} ENTRY {t.direction.name} @ {t.entry_price}")

        except Exception as e:
            print(f"[{bot['id']}] error processing {symbol}: {e}")


def main():
    print("Live paper-trading runner started. Ctrl+C to stop.")
    while True:
        bots_cfg = load_bots()
        secrets_cfg = load_secrets()
        for bot in bots_cfg["bots"]:
            if bot.get("active"):
                process_bot(bot, secrets_cfg)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
