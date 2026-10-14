# algobot

Multi-bot algo trading system — "Hilega Milega" strategy (RSI/EMA/WMA based),
6 bot types (intraday stock, intraday option, carry-forward futures,
carry-forward swing stock, carry-forward commodity options, carry-forward
commodity futures), Kite Connect sandbox for paper trading, Streamlit
control panel.

## Project layout

```
engine/        indicator math + entry/exit/SL/TSL strategy state machine
broker/        Kite Connect adapter (sandbox by default; flip one flag for live)
backtest/      historical backtest runner (pulls sandbox history, prints trade log)
dashboard/     Streamlit UI — Broker Login, Create Bot, Bots & Monitoring
config/        bots.yaml (bot definitions) + secrets.yaml (LOCAL ONLY, gitignored)
data/          trade logs written here at runtime (gitignored)
```

## First-time setup (local machine)

```bash
cd C:\Amit\Projects\Algos\algobot
pip install -r requirements.txt --break-system-packages
streamlit run dashboard/app.py
```

Opens at `http://localhost:8501`.

## Important: `config/secrets.yaml`

This file holds your broker API keys and (optionally) TOTP secret for
auto-login. It is created locally the first time you save credentials from
the Broker Login page, and it is in `.gitignore` — it will never be pushed
to GitHub. **Every machine that runs this bot (your laptop, later a VPS)
needs its own `config/secrets.yaml` created locally there** — cloning the
repo does not bring your keys with it, by design.

## Workflow across machines

```bash
# after making changes locally
git add .
git commit -m "describe the change"
git push

# on another machine (e.g. a VPS later)
git clone https://github.com/amitchcal/algobot.git
cd algobot
pip install -r requirements.txt --break-system-packages
# then set up config/secrets.yaml fresh on that machine via the dashboard
```

## Status

- [x] Indicator reconstruction (RSI(9), EMA(3)-of-RSI, WMA(21)-of-volume-RSI) —
      flagged as an assumption pending verification against the live
      TradingView "Hilega Milega" script
- [x] Strategy engine: crossover + sustain entry, EMA(9) SL, configurable TSL, open target
- [x] Kite sandbox broker adapter
- [x] Backtest runner
- [x] Streamlit dashboard: Broker Login / Create Bot / Bots & Monitoring, all 6 bot types
- [ ] Order-placement logic branched per bot type (options strike/expiry resolution,
      futures contract rollover, MCX commodity instrument lookup) — only the
      plain-equity path is proven so far
- [ ] Chartink scan formula verified against real indicator (Path A)
- [ ] Auto-login script (TOTP-based daily access-token refresh) for VPS deployment
