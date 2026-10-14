"""
Edit, activate/deactivate, and monitor every configured bot. This is the
page you'll come back to most often day-to-day: flip a bot on/off, adjust
capital or TSL without re-creating it, and check paper/live P&L.
"""

import os
import sys
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config.store import load_bots, save_bots, BOT_TYPES, COMMODITIES, ROOT

st.set_page_config(page_title="Bots & Monitoring", layout="wide")
st.title("📊 Bots & Monitoring")

bots_cfg = load_bots()
DATA_DIR = os.path.join(ROOT, "data")

if not bots_cfg["bots"]:
    st.info("No bots yet — create one from ➕ Create Bot.")
    st.stop()

# ---- portfolio-level summary ------------------------------------------
total_capital = sum(b["capital_deployed"] for b in bots_cfg["bots"])
active_capital = sum(b["capital_deployed"] for b in bots_cfg["bots"] if b["active"])
c1, c2, c3 = st.columns(3)
c1.metric("Total bots", len(bots_cfg["bots"]))
c2.metric("Active bots", sum(1 for b in bots_cfg["bots"] if b["active"]))
c3.metric("Capital allocated (active bots)", f"₹{active_capital:,.0f}")

st.divider()

for bot in bots_cfg["bots"]:
    meta = BOT_TYPES[bot["bot_type"]]
    status = "🟢 active" if bot["active"] else "⚪ inactive"
    mode = "📝 paper" if bot["paper_mode"] else "💰 LIVE"
    with st.expander(f"{bot['label']}  —  {status}  —  {mode}", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            bot["active"] = st.toggle("Active", value=bot["active"], key=f"active_{bot['id']}")
            bot["paper_mode"] = st.toggle("Paper mode", value=bot["paper_mode"], key=f"paper_{bot['id']}")
            if not bot["paper_mode"]:
                st.error("LIVE mode — this bot will place real orders with real money.")
            st.caption(f"{meta['exchange']} / {meta['segment']} / {meta['product']}")
        with col2:
            bot["capital_deployed"] = st.number_input(
                "Capital deployed (₹)", min_value=0, step=5000,
                value=int(bot["capital_deployed"]), key=f"cap_{bot['id']}")
            bot["lot_size"] = st.number_input(
                "Lot size", min_value=1, step=1,
                value=int(bot["lot_size"]), key=f"lot_{bot['id']}")
            bot["max_daily_loss"] = st.number_input(
                "Max daily loss (₹)", min_value=0, step=1000,
                value=int(bot["max_daily_loss"]), key=f"mdl_{bot['id']}")
        with col3:
            bot["tsl"]["mode"] = st.selectbox(
                "TSL mode", ["percent", "points"],
                index=["percent", "points"].index(bot["tsl"]["mode"]),
                key=f"tslmode_{bot['id']}")
            bot["tsl"]["trail_value"] = st.number_input(
                "TSL trail value", min_value=0.0, step=0.1,
                value=float(bot["tsl"]["trail_value"]), key=f"tslval_{bot['id']}")
            bot["tsl"]["activate_after"] = st.number_input(
                "TSL activates after", min_value=0.0, step=0.1,
                value=float(bot["tsl"]["activate_after"]), key=f"tslact_{bot['id']}")

        if bot["bot_type"] in ("intraday_stock", "carry_forward_swing_stock"):
            watchlist_str = st.text_input(
                "Watchlist (comma-separated tradingsymbols — full universe auto-scan not wired up yet)",
                value=", ".join(bot.get("watchlist", [])), key=f"wl_{bot['id']}")
            bot["watchlist"] = [s.strip().upper() for s in watchlist_str.split(",") if s.strip()]

        if meta["needs_commodity_select"]:
            bot["commodity_symbols"] = st.multiselect(
                "Commodities", options=[c["symbol"] for c in COMMODITIES],
                format_func=lambda s: next(c["label"] for c in COMMODITIES if c["symbol"] == s),
                default=bot.get("commodity_symbols", []), key=f"comm_{bot['id']}")

        colA, colB = st.columns(2)
        with colA:
            bot["trading_window"]["start"] = st.text_input(
                "Window start", value=bot["trading_window"]["start"], key=f"wstart_{bot['id']}")
        with colB:
            bot["trading_window"]["end"] = st.text_input(
                "Window end", value=bot["trading_window"]["end"], key=f"wend_{bot['id']}")

        trade_log_path = os.path.join(DATA_DIR, f"trades_{bot['id']}.csv")
        if os.path.exists(trade_log_path):
            trades = pd.read_csv(trade_log_path)
            total_pnl = trades["pnl"].sum() if "pnl" in trades.columns else 0
            win_rate = (trades["pnl"] > 0).mean() * 100 if "pnl" in trades.columns and len(trades) else 0
            m1, m2 = st.columns(2)
            m1.metric("P&L (₹)", f"{total_pnl:,.2f}")
            m2.metric("Win rate", f"{win_rate:.1f}%")
            st.dataframe(trades.tail(20), use_container_width=True)
        else:
            st.caption("No trade log yet — appears once the bot has run.")

        if st.button("🗑️ Delete this bot", key=f"delete_{bot['id']}"):
            bots_cfg["bots"] = [b for b in bots_cfg["bots"] if b["id"] != bot["id"]]
            save_bots(bots_cfg)
            st.rerun()

st.divider()
if st.button("Save all changes", type="primary"):
    save_bots(bots_cfg)
    st.success("Saved.")
