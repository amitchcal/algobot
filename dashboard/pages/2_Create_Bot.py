"""
Create a new bot of one of the 6 supported types. Fields shown adapt to the
chosen type (e.g. commodity selection and expiry/strike only appear for the
bot types that need them).
"""

import os
import sys
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config.store import (
    load_bots, save_bots, load_secrets, new_bot_id,
    BOT_TYPES, BROKERS, COMMODITIES,
)

st.set_page_config(page_title="Create Bot", layout="wide")
st.title("➕ Create Bot")

bots_cfg = load_bots()
secrets_cfg = load_secrets()
existing_ids = [b["id"] for b in bots_cfg["bots"]]

bot_type = st.selectbox(
    "Bot type", list(BOT_TYPES.keys()),
    format_func=lambda k: BOT_TYPES[k]["label"],
)
meta = BOT_TYPES[bot_type]

st.caption(
    f"Exchange: **{meta['exchange']}**  |  Segment: **{meta['segment']}**  |  "
    f"Product: **{meta['product']}**  |  "
    f"{'Carry forward (overnight)' if meta['carry_forward'] else 'Intraday — auto square-off required'}"
)

label = st.text_input("Bot name / label", value=meta["label"])

col1, col2 = st.columns(2)
with col1:
    brokers_available = list(secrets_cfg.get("brokers", {}).keys()) or BROKERS
    broker = st.selectbox("Broker", brokers_available,
                           format_func=lambda b: b.replace("_", " ").title())
    if broker not in secrets_cfg.get("brokers", {}):
        st.warning("This broker has no saved credentials yet — set it up on the Broker Login page before activating this bot.")
    paper_mode = st.toggle("Paper mode (sandbox)", value=True,
                            help="Keep ON until you've validated results. Switching OFF places real orders.")
    capital_deployed = st.number_input("Capital deployed (₹)", min_value=0, step=5000, value=50000,
                                        help="Fund blocked for this bot specifically. Execution still depends on actual fund availability at order time.")
    lot_size = st.number_input("Lot size / quantity multiplier", min_value=1, step=1, value=1)

with col2:
    tsl_mode = st.selectbox("TSL mode", ["percent", "points"])
    tsl_value = st.number_input("TSL trail value", min_value=0.0, step=0.1, value=1.0)
    tsl_activate_after = st.number_input(
        "TSL activates after (profit %, or points — matches TSL mode)",
        min_value=0.0, step=0.1, value=0.0)
    max_daily_loss = st.number_input("Max daily loss (₹) — bot pauses if breached", min_value=0, step=1000, value=5000)

commodity_symbols = []
if meta["needs_commodity_select"]:
    st.subheader("Commodity selection")
    chosen = st.multiselect(
        "Commodities this bot trades",
        options=[c["symbol"] for c in COMMODITIES],
        format_func=lambda s: next(c["label"] for c in COMMODITIES if c["symbol"] == s),
        default=[COMMODITIES[0]["symbol"]],
    )
    commodity_symbols = chosen

expiry_preference = None
strike_selection = None
if meta["needs_expiry"]:
    expiry_preference = st.selectbox("Expiry preference", ["weekly", "monthly"],
                                      index=0 if meta["segment"] != "Commodity Options" else 1)
if meta["needs_strike_select"]:
    strike_selection = st.selectbox("Strike selection", ["ATM", "ITM1", "ITM2", "OTM1", "OTM2"])

st.subheader("Trading window")
colA, colB = st.columns(2)
with colA:
    start_time = st.text_input("Start (HH:MM)", value="16:00" if meta["exchange"] == "MCX" else "09:20")
with colB:
    end_time = st.text_input("End (HH:MM)", value="23:30" if meta["exchange"] == "MCX" else "15:15")

st.subheader("Strategy")
strategy = st.selectbox("Strategy", ["hilega_milega"], help="More strategies can be added here as you build them.")

active = st.toggle("Activate immediately on creation", value=False)

if st.button("Create bot", type="primary"):
    bot_id = new_bot_id(bot_type, existing_ids)
    new_bot = {
        "id": bot_id,
        "bot_type": bot_type,
        "label": label,
        "active": active,
        "broker": broker,
        "paper_mode": paper_mode,
        "strategy": strategy,
        "capital_deployed": capital_deployed,
        "lot_size": lot_size,
        "commodity_symbols": commodity_symbols,
        "expiry_preference": expiry_preference,
        "strike_selection": strike_selection,
        "tsl": {"mode": tsl_mode, "trail_value": tsl_value, "activate_after": tsl_activate_after},
        "trading_window": {"start": start_time, "end": end_time},
        "max_daily_loss": max_daily_loss,
    }
    bots_cfg["bots"].append(new_bot)
    save_bots(bots_cfg)
    st.success(f"Created bot `{bot_id}`. Manage it from 📊 Bots & Monitoring.")
    st.rerun()
