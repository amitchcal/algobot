# Chartink scan formulas — Hilega Milega, 3 scanners

## Subscription note

Free tier works for manual 15-min checking — ~5-minute data delay, which is
inside your own checking cadence. Premium (~₹780/mo) only matters if you
later want SMS/webhook alerts or sub-5-minute timeframes. Source:
https://www.strike.money/reviews/chartink (Jan 2026 pricing, verify on
chartink.com before paying — prices drift).

## Honest limitation (applies to all 3 scanners below)

Chartink has no `wma()` function and no way to upload a custom composite
indicator, so the red "volume" line (our WMA(21)-of-volume-RSI
reconstruction) can't be replicated exactly. All 3 scanners below
approximate it with `volume > sma(volume,20) * 1.2` (above-average volume)
instead. Treat these as a **first-pass shortlist filter** — the precise
three-line entry/exit decision still happens in `engine/strategy.py` once a
symbol is shortlisted. The `rsi(9)` vs `ema(3, rsi(9))` crossover (black vs
green) IS natively supported and should be accurate.

**Unverified syntax detail:** Chartink's intraday scans use a per-scan
"minutes" interval dropdown (5/10/15/30/60) rather than period keywords in
the formula text. Whether `1 day ago` then means "1 bar of the selected
interval ago" (Chartink's usual convention) or literally 1 calendar day, I
haven't been able to confirm against a live Chartink session. **Run scanner
1 once, check that it fires on a real same-candle crossover before trusting
it** — if `1 day ago` doesn't behave as "1 bar ago" on your account, drop
that clause and rely on the UI's own "show only fresh crossovers" option if
it has one.

---

## 1. Intraday stocks (bots 1 & 2 — Nifty 500)

Setup: Scanner → Create Scan → set **Minutes = 15** → Group = **Nifty 500**.

Bullish:
```
( {cash} ( latest rsi(9) > latest ema(3, rsi(9)) and
           1 day ago rsi(9) <= 1 day ago ema(3, rsi(9)) and
           latest volume > latest sma(volume,20) * 1.2 and
           latest close > latest ema(9,close) ) )
```
Bearish:
```
( {cash} ( latest rsi(9) < latest ema(3, rsi(9)) and
           1 day ago rsi(9) >= 1 day ago ema(3, rsi(9)) and
           latest volume > latest sma(volume,20) * 1.2 and
           latest close < latest ema(9,close) ) )
```

## 2. Swing stocks (bot 4 — NSE, daily)

Setup: Scanner → Create Scan → leave as **Daily (EOD)** → Group = **All NSE**
(or Nifty 500 if you want to narrow it, per your bot config note).

Bullish:
```
( {cash} ( latest rsi(9) > latest ema(3, rsi(9)) and
           1 day ago rsi(9) <= 1 day ago ema(3, rsi(9)) and
           latest volume > latest sma(volume,20) * 1.2 and
           latest close > latest ema(9,close) ) )
```
Bearish:
```
( {cash} ( latest rsi(9) < latest ema(3, rsi(9)) and
           1 day ago rsi(9) >= 1 day ago ema(3, rsi(9)) and
           latest volume > latest sma(volume,20) * 1.2 and
           latest close < latest ema(9,close) ) )
```
(Identical formula to #1 — only the Minutes/Daily setting and the Group
selector differ. Chartink applies the same query text differently depending
on those two UI controls.)

## 3. Derivative (F&O) stocks (bot 3 — futures)

Setup: Scanner → Create Scan → **Minutes = 15** (or Daily, matching
whichever timeframe you want futures signals on) → Group = **F&O Stocks**.

Bullish:
```
( {cash} ( latest rsi(9) > latest ema(3, rsi(9)) and
           1 day ago rsi(9) <= 1 day ago ema(3, rsi(9)) and
           latest volume > latest sma(volume,20) * 1.2 and
           latest close > latest ema(9,close) ) )
```
Bearish:
```
( {cash} ( latest rsi(9) < latest ema(3, rsi(9)) and
           1 day ago rsi(9) >= 1 day ago ema(3, rsi(9)) and
           latest volume > latest sma(volume,20) * 1.2 and
           latest close < latest ema(9,close) ) )
```
Note: this scans the **underlying cash stock's** price action (Chartink
scans equities, not derivative contracts directly) — you'd then take the
signal and trade the corresponding futures contract manually or via the
engine once futures contract-resolution is built.

## Indices (bot not yet defined for this)

Chartink doesn't scan indices as a group — if you want a Nifty/Bank Nifty
index-level signal, that's a separate single-symbol scan against `NSE:NIFTY`
/ `NSE:BANKNIFTY`, not a universe scan. Tell me if you want this as a 4th
scanner.

## Validating against the real indicator

Once you've run these a few times, compare shortlisted names against the
actual "Hilega Milega" TradingView indicator on a couple of symbols. Any
case where Chartink's volume proxy clearly disagrees with the real red
line — note it, and we tighten the approximation.
