"""
First-time broker login / API key setup.

Stores credentials in config/secrets.yaml (0600 permissions, gitignored —
never put this file in version control or send it anywhere). This page
only SAVES the keys; the actual daily access-token refresh (the auto-login
script using a stored TOTP secret) is a separate scheduled script meant to
run on your VPS each morning — see README for that piece. Keeping this UI
and that script reading the same secrets.yaml means you only enter your
keys once here.
"""

import os
import sys
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config.store import load_secrets, save_secrets, BROKERS

st.set_page_config(page_title="Broker Login", layout="wide")
st.title("🔑 Broker Login — First-Time Setup")

st.warning(
    "Credentials are saved locally to `config/secrets.yaml` on this "
    "machine only, never transmitted anywhere else by this app. Still, "
    "treat that file like a password: don't commit it to git, don't share "
    "it, and delete it if you decommission this setup."
)

secrets_cfg = load_secrets()
secrets_cfg.setdefault("brokers", {})

broker = st.selectbox("Broker", BROKERS, format_func=lambda b: b.replace("_", " ").title())
existing = secrets_cfg["brokers"].get(broker, {})

st.subheader(f"{broker.replace('_', ' ').title()} credentials")

col1, col2 = st.columns(2)
with col1:
    api_key = st.text_input("API Key", value=existing.get("api_key", ""), type="password")
    api_secret = st.text_input("API Secret", value=existing.get("api_secret", ""), type="password")
    client_id = st.text_input("Client ID / User ID", value=existing.get("client_id", ""))
with col2:
    password = st.text_input("Login Password", value="", type="password",
                              help="Needed only if you set up auto-login (TOTP-based). Leave blank to log in manually each morning.")
    totp_secret = st.text_input("TOTP Secret (for auto-login)", value=existing.get("totp_secret", ""),
                                 type="password",
                                 help="The base32 secret from your authenticator app's QR setup — NOT the 6-digit code itself.")
    paper_mode = st.toggle("Paper mode (sandbox)", value=existing.get("paper_mode", True))

st.caption(
    "Leave Password / TOTP Secret blank if you plan to log in manually each "
    "trading day. Fill them in only if you want the scheduled auto-login "
    "script to refresh your access token unattended every morning."
)

if st.button("Save broker credentials", type="primary"):
    secrets_cfg["brokers"][broker] = {
        "api_key": api_key,
        "api_secret": api_secret,
        "client_id": client_id,
        "password": password,
        "totp_secret": totp_secret,
        "paper_mode": paper_mode,
        "access_token": existing.get("access_token", ""),  # filled by daily login script
    }
    save_secrets(secrets_cfg)
    st.success(f"Saved {broker} credentials.")

st.divider()
st.subheader("Today's session status")
access_token = secrets_cfg["brokers"].get(broker, {}).get("access_token", "")
if access_token:
    st.success("Access token present for today — bot engine can place orders.")
else:
    st.error(
        "No access token yet for today. Either run the daily auto-login "
        "script, or log in manually via your broker's Kite Connect login "
        "URL and paste the resulting access token below."
    )
    manual_token = st.text_input("Paste today's access token manually")
    if st.button("Save access token"):
        secrets_cfg["brokers"].setdefault(broker, {})["access_token"] = manual_token
        save_secrets(secrets_cfg)
        st.success("Access token saved for today.")

st.divider()
st.subheader("Brokers configured")
if secrets_cfg["brokers"]:
    for b in secrets_cfg["brokers"]:
        st.markdown(f"- **{b}** — {'🟢 token set' if secrets_cfg['brokers'][b].get('access_token') else '⚪ no token yet today'}")
else:
    st.caption("None yet.")
