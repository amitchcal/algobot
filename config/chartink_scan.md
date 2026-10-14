# Chartink scan formula — Hilega Milega shortlist

## Honest limitation first

Chartink's scanner query language natively supports `rsi()`, `ema()`, `sma()`,
`macd()`, `supertrend()`, `bollinger bands`, `atr()`, `obv()` and basic
price/volume fields — but **it has no `wma()` function** and no way to upload
a custom composite indicator (like our reconstructed volume-RSI-smoothed-by-
WMA red line). So the scan below can faithfully replicate the **black/green**
portion (RSI(9) and its EMA(3) signal), but the **red "volume" line** has to
be approximated with Chartink's native volume tools — it will not be an exact
match to the real TradingView indicator's red line. Treat this scan as a
**first-pass universe filter** (narrow 500+ stocks down to a shortlist), with
the full three-line logic (engine/strategy.py) doing the precise entry/exit
decision once a symbol is shortlisted.

## Scan formula (paste into Chartink's scanner query box)

**Bullish shortlist (long candidates):**
```
( {cash} ( latest rsi(9) > latest ema(3, rsi(9)) and
           1 day ago rsi(9) <= 1 day ago ema(3, rsi(9)) and
           latest volume > latest sma(volume,20) * 1.2 and
           latest close > latest ema(9,close) ) )
```

**Bearish shortlist (short candidates):**
```
( {cash} ( latest rsi(9) < latest ema(3, rsi(9)) and
           1 day ago rsi(9) >= 1 day ago ema(3, rsi(9)) and
           latest volume > latest sma(volume,20) * 1.2 and
           latest close < latest ema(9,close) ) )
```

What each line does:
- `rsi(9) vs ema(3, rsi(9))` crossing — proxy for the black/green crossover
- `1 day ago` comparison — ensures this is the crossover candle, not an
  already-crossed state (fires once, not every day it stays crossed)
- `volume > sma(volume,20) * 1.2` — stand-in for the red "volume" filter:
  flags above-average volume (1.2x 20-period average) instead of the true
  volume-RSI reconstruction
- `close vs ema(9,close)` — mirrors the SL reference, so shortlisted names
  are already on the correct side of their SL line at scan time

Swap `1 day ago` for the appropriate Chartink period if scanning the
**15-minute** timeframe (Chartink's intraday scanner uses its own period
syntax — confirm via its UI, since this varies by plan).

## Universe filters

Append one of these to scope the scan:
- **Nifty 500:** `latest close > 0 and market cap > 0` is not a filter —
  instead use Chartink's built-in "Nifty 500" group selector in the scanner
  UI (top-left dropdown), not a formula clause.
- **F&O stocks:** use Chartink's "F&O" group selector the same way.
- **Indices:** Chartink scans equities, not indices directly — index-level
  conditions (Nifty, Bank Nifty, Sensex) need to be run as a separate scan
  against the index symbol itself (e.g. `NSE:NIFTY`), not the group selector.

## Recommended next step

Once you're ready, open Chartink's scanner, paste the bullish formula, and
compare its shortlist against a few symbols checked manually against the
real "Hilega Milega" TradingView indicator. That comparison is what lets us
correct the volume-line approximation — screenshot or note any shortlisted
stock where the real indicator clearly disagrees with this scan's volume
proxy, and we tighten the formula from there.
