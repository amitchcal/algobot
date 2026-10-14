"""
Shared config I/O + bot-type metadata, used by every dashboard page and by
the live engine. Single source of truth so the UI and the engine never
disagree about what a "bot type" implies (segment, product, exchange).

Two separate files on disk:
    config/bots.yaml     - bot definitions (safe to view/share/commit)
    config/secrets.yaml  - broker credentials (NEVER commit this file -
                            add it to .gitignore; kept separate on purpose
                            so bots.yaml can be shared/backed up freely)
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Optional, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOTS_PATH = os.path.join(ROOT, "config", "bots.yaml")
SECRETS_PATH = os.path.join(ROOT, "config", "secrets.yaml")

COMMODITIES = [
    {"label": "Crude Oil", "symbol": "CRUDEOIL"},
    {"label": "Natural Gas", "symbol": "NATURALGAS"},
    {"label": "Silver Mini", "symbol": "SILVERM"},
    {"label": "Gold Mini", "symbol": "GOLDM"},
]

# ---- bot-type catalogue --------------------------------------------------
# Each type fixes the segment/exchange/product so the UI only asks for
# fields that are actually relevant to that bot, and the engine always
# routes orders to the right exchange/product combination.

BOT_TYPES = {
    "intraday_stock": {
        "label": "Intraday Stock Trading (Nifty 500)",
        "exchange": "NSE",
        "segment": "Equity",
        "product": "MIS",
        "universe": "nifty500",
        "carry_forward": False,
        "needs_commodity_select": False,
        "needs_expiry": False,
        "needs_strike_select": False,
    },
    "intraday_option": {
        "label": "Intraday Option Trading",
        "exchange": "NFO",
        "segment": "Options",
        "product": "MIS",
        "universe": "fno",
        "carry_forward": False,
        "needs_commodity_select": False,
        "needs_expiry": True,
        "needs_strike_select": True,
    },
    "carry_forward_futures": {
        "label": "Carry Forward Futures Trading",
        "exchange": "NFO",
        "segment": "Futures",
        "product": "NRML",
        "universe": "fno",
        "carry_forward": True,
        "needs_commodity_select": False,
        "needs_expiry": True,
        "needs_strike_select": False,
    },
    "carry_forward_swing_stock": {
        "label": "Carry Forward Swing Stock Trading (NSE stocks)",
        "exchange": "NSE",
        "segment": "Equity",
        "product": "NRML",   # CNC/NRML depending on your broker's naming
        "universe": "nse_all",   # broadened from nifty500 per user's note
        "carry_forward": True,
        "needs_commodity_select": False,
        "needs_expiry": False,
        "needs_strike_select": False,
    },
    "carry_forward_commodity_option": {
        "label": "Carry Forward Commodity Option Trading",
        "exchange": "MCX",
        "segment": "Commodity Options",
        "product": "NRML",
        "universe": "commodity",
        "carry_forward": True,
        "needs_commodity_select": True,
        "needs_expiry": True,
        "needs_strike_select": True,
    },
    "carry_forward_commodity_futures": {
        "label": "Carry Forward Commodity Futures Trading",
        "exchange": "MCX",
        "segment": "Commodity Futures",
        "product": "NRML",
        "universe": "commodity",
        "carry_forward": True,
        "needs_commodity_select": True,
        "needs_expiry": True,
        "needs_strike_select": False,
    },
}

BROKERS = ["zerodha_kite", "upstox", "fyers", "angel_one_smartapi"]


def default_bots_config():
    return {"bots": []}


def load_bots():
    if not os.path.exists(BOTS_PATH):
        return default_bots_config()
    with open(BOTS_PATH) as f:
        cfg = yaml.safe_load(f) or default_bots_config()
        cfg.setdefault("bots", [])
        return cfg


def save_bots(cfg):
    with open(BOTS_PATH, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)


def load_secrets():
    if not os.path.exists(SECRETS_PATH):
        return {"brokers": {}}
    with open(SECRETS_PATH) as f:
        return yaml.safe_load(f) or {"brokers": {}}


def save_secrets(cfg):
    # 0600 perms: owner read/write only, since this file holds credentials
    with open(SECRETS_PATH, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)
    os.chmod(SECRETS_PATH, 0o600)


def new_bot_id(bot_type: str, existing_ids: List[str]) -> str:
    base = bot_type
    i = 1
    candidate = f"{base}_{i}"
    while candidate in existing_ids:
        i += 1
        candidate = f"{base}_{i}"
    return candidate
