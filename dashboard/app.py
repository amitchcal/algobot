"""
Home page of the multi-bot control panel.

Run from the project root:
    streamlit run dashboard/app.py

Pages (left sidebar, auto-discovered by Streamlit from dashboard/pages/):
    1 - Broker Login       first-time API key / TOTP setup, per broker
    2 - Create Bot         add one of the 6 bot types with its inputs
    3 - Bots & Monitoring  edit/activate existing bots, view paper P&L
"""

import os
import sys
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.store import load_bots, load_secrets, BOT_TYPES

st.set_page_config(page_title="Algo Bots — Control Panel", layout="wide")
st.title("Algo Trading — Control Panel")

st.markdown(
    "Use the sidebar to log in your broker, create bots, and monitor them. "
    "All bots run in **paper mode (Kite sandbox)** until you switch a bot "
    "to live from the Bots & Monitoring page."
)

bots_cfg = load_bots()
secrets_cfg = load_secrets()

c1, c2, c3 = st.columns(3)
c1.metric("Bots configured", len(bots_cfg["bots"]))
c2.metric("Active bots", sum(1 for b in bots_cfg["bots"] if b.get("active")))
c3.metric("Brokers logged in", len(secrets_cfg.get("brokers", {})))

st.divider()
st.subheader("Bot types available")
for key, meta in BOT_TYPES.items():
    st.markdown(f"- **{meta['label']}**  —  {meta['exchange']} / {meta['segment']} / product `{meta['product']}`")

st.divider()
if not secrets_cfg.get("brokers"):
    st.warning("No broker is set up yet. Go to **🔑 Broker Login** first.")
elif not bots_cfg["bots"]:
    st.info("No bots yet. Go to **➕ Create Bot** to add your first one.")
else:
    st.success("Setup looks good — manage bots from **📊 Bots & Monitoring**.")
