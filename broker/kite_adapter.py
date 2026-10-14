"""
Thin broker adapter over KiteConnect.

Points at the Kite Connect SANDBOX by default (sandbox.kite.trade) so the
whole engine can be developed and paper-traded with zero real-money risk.
Flipping to a live account later is a one-line config change (PAPER_MODE =
False + real api_key/api_secret/access_token), not a rewrite - every other
module in this project only talks to this adapter, never to KiteConnect
directly.

Requires: pip install kiteconnect
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd

try:
    from kiteconnect import KiteConnect, KiteTicker
except ImportError:
    KiteConnect = None
    KiteTicker = None


SANDBOX_ROOT = "https://sandbox.kite.trade"
SANDBOX_WS_ROOT = "wss://ws-sandbox.kite.trade"
LIVE_ROOT = "https://api.kite.trade"


@dataclass
class BrokerConfig:
    api_key: str
    access_token: str
    paper_mode: bool = True        # True -> sandbox, False -> live account
    api_secret: Optional[str] = None


class KiteAdapter:
    def __init__(self, cfg: BrokerConfig):
        if KiteConnect is None:
            raise ImportError("Run: pip install kiteconnect --break-system-packages")
        self.cfg = cfg
        root = SANDBOX_ROOT if cfg.paper_mode else LIVE_ROOT
        self.kite = KiteConnect(api_key=cfg.api_key, root=root)
        self.kite.set_access_token(cfg.access_token)

    # ---- market data --------------------------------------------------

    def historical_data(self, instrument_token: int, from_date, to_date,
                         interval: str) -> pd.DataFrame:
        """interval: 'minute','15minute','day', etc."""
        candles = self.kite.historical_data(
            instrument_token, from_date, to_date, interval
        )
        df = pd.DataFrame(candles)
        df = df.rename(columns={"date": "timestamp"})
        df = df.set_index("timestamp")
        return df[["open", "high", "low", "close", "volume"]]

    def instruments(self, exchange: str = "NSE"):
        return self.kite.instruments(exchange=exchange)

    def quote(self, symbols: list):
        return self.kite.quote(symbols)

    def ticker(self):
        """Returns a KiteTicker pointed at the correct (sandbox/live) WS root."""
        ws_root = SANDBOX_WS_ROOT if self.cfg.paper_mode else None
        kws = KiteTicker(self.cfg.api_key, self.cfg.access_token,
                          root=ws_root) if ws_root else KiteTicker(
            self.cfg.api_key, self.cfg.access_token)
        return kws

    # ---- orders ---------------------------------------------------------

    def place_order(self, tradingsymbol: str, exchange: str, transaction_type: str,
                     quantity: int, product: str = "MIS", order_type: str = "LIMIT",
                     price: Optional[float] = None, variety: str = "regular"):
        """
        NOTE: Kite sandbox only supports LIMIT orders for API order placement
        (no MARKET). Pass a sensible limit price (e.g. last traded price +/-
        a few paise) when paper trading. Live trading can use MARKET once
        paper_mode=False.
        """
        kwargs = dict(
            variety=variety,
            exchange=exchange,
            tradingsymbol=tradingsymbol,
            transaction_type=transaction_type,
            quantity=quantity,
            product=product,
            order_type="LIMIT" if self.cfg.paper_mode else order_type,
        )
        if price is not None or self.cfg.paper_mode:
            kwargs["price"] = price
        return self.kite.place_order(**kwargs)

    def positions(self):
        return self.kite.positions()

    def margins(self, segment: Optional[str] = None):
        return self.kite.margins(segment) if segment else self.kite.margins()

    def orders(self):
        return self.kite.orders()
