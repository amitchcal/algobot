"""
Indicator calculations for the "Hilega Milega" strategy.

Per the reference transcript (Profit Ladoo):
    - Black line : RSI(9)                 -> "strength / momentum"
    - Green line : "price action", 3 EMA
    - Red line   : "volume", 21 WMA
    - Signal rule: bullish when green crosses above red; bearish when green
      crosses below red; red must stay "within the RSI area" during a trade.

ASSUMPTION FLAGGED (dimensionally required, not yet confirmed against the
live TradingView script): for green and red to meaningfully cross each
other, and for red to sit "within" black's zone, all three lines must share
one 0-100 oscillator scale. A raw EMA(3) of close (price-scaled) cannot
cross a WMA(21) of volume (a different scale) in any meaningful way. The
only internally-consistent reconstruction is:

    black = RSI(9) of close                         [[the base oscillator]]
    green = EMA(3)  of that RSI(9)                   [[fast signal line]]
    red   = WMA(21) of a volume-RSI(9) (volume proxy)[[slow filter line]]

This keeps every line on 0-100 and makes every rule in the transcript
literally true (crossovers, "red within RSI area", "lines separated =
stronger momentum"). Swap VOLUME_PROXY_MODE, or the whole reconstruction,
once the real TradingView script is inspected - nothing else in the engine
depends on these exact formulas, only on rsi9/ema3_signal/vol_red existing
as three 0-100 series.

A separate EMA(9) of close is also computed: this is NOT one of the three
plotted lines. It exists purely as the user-specified stop-loss reference
("SL = closing price below EMA(9)").
"""

import pandas as pd
import numpy as np

VOLUME_PROXY_MODE = "volume_rsi"  # "volume_rsi" | "mfi"


def rsi(close: pd.Series, period: int = 9) -> pd.Series:
    """Classic Wilder RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)  # neutral before enough data / when avg_loss==0


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def wma(series: pd.Series, period: int) -> pd.Series:
    weights = np.arange(1, period + 1)

    def _wma(x):
        return np.dot(x, weights) / weights.sum()

    return series.rolling(period).apply(_wma, raw=True)


def volume_rsi(volume: pd.Series, period: int = 9) -> pd.Series:
    """RSI computed on volume deltas instead of price deltas."""
    delta = volume.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def money_flow_index(high, low, close, volume, period: int = 9) -> pd.Series:
    typical_price = (high + low + close) / 3
    raw_money_flow = typical_price * volume
    direction = typical_price.diff()
    pos_flow = raw_money_flow.where(direction > 0, 0.0)
    neg_flow = raw_money_flow.where(direction < 0, 0.0)
    pos_sum = pos_flow.rolling(period).sum()
    neg_sum = neg_flow.rolling(period).sum()
    money_ratio = pos_sum / neg_sum.replace(0, np.nan)
    out = 100 - (100 / (1 + money_ratio))
    return out.fillna(50)


def compute_hilega_milega(df: pd.DataFrame) -> pd.DataFrame:
    """
    df must have columns: open, high, low, close, volume (any case, will be
    lower-cased), indexed by datetime, one row per candle on the chosen
    timeframe (15-min for intraday, Daily for swing).

    Returns df with added columns, all comparable on one 0-100 scale:
        rsi9        - black line  (strength / base oscillator)
        ema3_signal - green line  (price action signal: EMA(3) of rsi9)
        vol_red     - red line    (volume filter: WMA(21) of a volume-RSI)
        ema9_sl     - separate, price-scaled EMA(9) used ONLY as the SL
                      reference (not one of the three plotted lines)
        cross       - +1 on the candle green crosses above red (bullish)
                      -1 on the candle green crosses below red (bearish)
                       0 otherwise
        in_band     - True when green sits between red and black (the
                      "sustain within red/green area" continuation zone)
        red_in_rsi_zone - True when red is within the black RSI's recent
                      range, the transcript's stated entry-validity filter
    """
    out = df.copy()
    out.columns = [c.lower() for c in out.columns]

    out["rsi9"] = rsi(out["close"], 9)
    out["ema3_signal"] = ema(out["rsi9"], 3)
    out["ema9_sl"] = ema(out["close"], 9)  # SL reference only, price-scaled

    if VOLUME_PROXY_MODE == "mfi":
        raw_vol_osc = money_flow_index(out["high"], out["low"], out["close"], out["volume"], 9)
    else:
        raw_vol_osc = volume_rsi(out["volume"], 9)
    out["vol_red"] = wma(raw_vol_osc, 21)

    green, red, black = out["ema3_signal"], out["vol_red"], out["rsi9"]

    prev_diff = (green.shift(1) - red.shift(1))
    curr_diff = (green - red)
    cross_up = (prev_diff <= 0) & (curr_diff > 0)
    cross_down = (prev_diff >= 0) & (curr_diff < 0)
    out["cross"] = np.select([cross_up, cross_down], [1, -1], default=0)

    lo = pd.concat([green, red], axis=1).min(axis=1)
    hi = pd.concat([green, red], axis=1).max(axis=1)
    out["in_band"] = (green >= lo) & (green <= hi) & (red >= lo) & (red <= hi)

    # "red must remain within the RSI area" -> red within black's recent
    # (20-bar) trading range, used as an entry-validity / strength filter
    rsi_roll_lo = black.rolling(20).min()
    rsi_roll_hi = black.rolling(20).max()
    out["red_in_rsi_zone"] = (red >= rsi_roll_lo) & (red <= rsi_roll_hi)

    out["lines_separated"] = (
        (abs(black - green) > 2) & (abs(green - red) > 2) & (abs(black - red) > 2)
    )

    return out
