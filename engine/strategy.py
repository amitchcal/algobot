"""
Hilega Milega strategy engine: entry / exit / SL / TSL state machine.

Entry rules (as specified by the user):
    - Fires ON THE SAME CANDLE the crossover happens (no confirmation delay).
    - Also fires on "sustain": green line sitting within the red/black band
      on candles after the initial cross, i.e. continuation entries while
      momentum is still intact, not only on the first crossover candle.

Exit rules:
    - Hard SL: close price crosses to the wrong side of EMA(9)
        long  SL  -> close < ema9_sl
        short SL  -> close > ema9_sl
    - TSL: configurable trailing stop, applied once in profit (see
      TSLConfig). No fixed target - "open target": the trade rides until
      SL or TSL exits it.

This module is timeframe-agnostic: feed it 15-min candles for intraday or
daily candles for swing, it does not care. It is also broker-agnostic: it
emits Signal/Trade objects, the broker adapter is responsible for turning
those into real or paper orders.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
import pandas as pd

from .indicators import compute_hilega_milega


class Direction(Enum):
    LONG = 1
    SHORT = -1


class ExitReason(Enum):
    SL_EMA9 = "sl_ema9"
    TSL = "trailing_stop"
    EOD_SQUAREOFF = "eod_squareoff"


@dataclass
class TSLConfig:
    """Trailing stop-loss configuration. All values configurable per bot."""
    mode: str = "percent"          # "percent" | "points"
    trail_value: float = 1.0       # % or points, depending on mode
    activate_after: float = 0.0    # profit (in %, or points, matching mode)
    # before trailing engages. 0 = trail from entry immediately.


@dataclass
class Trade:
    symbol: str
    direction: Direction
    entry_time: pd.Timestamp
    entry_price: float
    qty: int
    sl_price: float                 # current SL (EMA9-based, updates each bar)
    tsl_price: Optional[float] = None
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[ExitReason] = None
    max_favorable_price: float = field(default=0.0)

    @property
    def is_open(self) -> bool:
        return self.exit_time is None

    def pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        sign = 1 if self.direction == Direction.LONG else -1
        return sign * (self.exit_price - self.entry_price) * self.qty

    def pnl_pct(self) -> float:
        if self.exit_price is None:
            return 0.0
        sign = 1 if self.direction == Direction.LONG else -1
        return sign * (self.exit_price - self.entry_price) / self.entry_price * 100


class HilegaMilegaStrategy:
    def __init__(self, symbol: str, qty: int, tsl_config: TSLConfig,
                 intraday_squareoff_time: Optional[str] = "15:15"):
        self.symbol = symbol
        self.qty = qty
        self.tsl_config = tsl_config
        self.intraday_squareoff_time = intraday_squareoff_time
        self.open_trade: Optional[Trade] = None
        self.closed_trades: List[Trade] = []

    # ---- signal detection -------------------------------------------------

    def _entry_signal(self, row) -> Optional[Direction]:
        """Entry on crossover candle, or sustain entry inside the band,
        gated by the red-line-within-RSI-zone strength filter."""
        if not row["red_in_rsi_zone"]:
            return None

        if row["cross"] == 1:
            return Direction.LONG
        if row["cross"] == -1:
            return Direction.SHORT

        # sustain entry: no fresh cross, but green still sitting inside the
        # band formed by red/black -> momentum intact, allow continuation
        if row["in_band"]:
            if row["ema3_signal"] > row["vol_red"]:
                return Direction.LONG
            elif row["ema3_signal"] < row["vol_red"]:
                return Direction.SHORT
        return None

    def _update_tsl(self, trade: Trade, price: float):
        cfg = self.tsl_config
        sign = 1 if trade.direction == Direction.LONG else -1
        trade.max_favorable_price = (
            max(trade.max_favorable_price, price) if trade.direction == Direction.LONG
            else min(trade.max_favorable_price or price, price)
        )

        move = sign * (trade.max_favorable_price - trade.entry_price)
        move_pct = move / trade.entry_price * 100

        activated = (move_pct if cfg.mode == "percent" else move) >= cfg.activate_after
        if not activated:
            return

        if cfg.mode == "percent":
            trail_amount = trade.max_favorable_price * (cfg.trail_value / 100)
        else:
            trail_amount = cfg.trail_value

        new_tsl = trade.max_favorable_price - sign * trail_amount
        if trade.tsl_price is None:
            trade.tsl_price = new_tsl
        else:
            if trade.direction == Direction.LONG:
                trade.tsl_price = max(trade.tsl_price, new_tsl)
            else:
                trade.tsl_price = min(trade.tsl_price, new_tsl)

    def _check_exit(self, trade: Trade, row) -> Optional[ExitReason]:
        close = row["close"]
        if trade.direction == Direction.LONG:
            if close < row["ema9_sl"]:
                return ExitReason.SL_EMA9
            if trade.tsl_price is not None and close <= trade.tsl_price:
                return ExitReason.TSL
        else:
            if close > row["ema9_sl"]:
                return ExitReason.SL_EMA9
            if trade.tsl_price is not None and close >= trade.tsl_price:
                return ExitReason.TSL
        return None

    # ---- main bar-by-bar loop ---------------------------------------------

    def on_bar(self, timestamp: pd.Timestamp, row):
        """Call once per closed candle, in chronological order."""
        if self.open_trade is not None:
            self._update_tsl(self.open_trade, row["close"])
            reason = self._check_exit(self.open_trade, row)

            squareoff = (
                self.intraday_squareoff_time is not None
                and timestamp.strftime("%H:%M") >= self.intraday_squareoff_time
            )
            if reason is None and squareoff:
                reason = ExitReason.EOD_SQUAREOFF

            if reason is not None:
                self.open_trade.exit_time = timestamp
                self.open_trade.exit_price = row["close"]
                self.open_trade.exit_reason = reason
                self.closed_trades.append(self.open_trade)
                self.open_trade = None

        if self.open_trade is None:
            direction = self._entry_signal(row)
            if direction is not None:
                self.open_trade = Trade(
                    symbol=self.symbol,
                    direction=direction,
                    entry_time=timestamp,
                    entry_price=row["close"],
                    qty=self.qty,
                    sl_price=row["ema9_sl"],
                    max_favorable_price=row["close"],
                )

    def run(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        """Run the strategy over a full historical dataframe (backtest mode)."""
        enriched = compute_hilega_milega(ohlcv)
        for ts, row in enriched.iterrows():
            self.on_bar(ts, row)
        return enriched
