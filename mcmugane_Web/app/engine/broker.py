from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta, timezone

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType, OrderClass
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

import pandas as pd

@dataclass
class AccountConfig:
    id: str
    broker: str  # "alpaca"
    name: str
    paper: bool
    api_key: str
    secret_key: str

class AlpacaBroker:
    def __init__(self, cfg: AccountConfig):
        self.cfg = cfg
        self.trading = TradingClient(cfg.api_key, cfg.secret_key, paper=cfg.paper)
        self.data = StockHistoricalDataClient(cfg.api_key, cfg.secret_key)

    def market_order(self, symbol: str, side: str, qty: Optional[float]=None, notional: Optional[float]=None,
                     tif: str="day", take_profit: Optional[float]=None, stop_loss: Optional[float]=None) -> Dict[str, Any]:
        tif_enum = TimeInForce(tif)
        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        req = MarketOrderRequest(symbol=symbol, side=side_enum, time_in_force=tif_enum)
        if qty is not None:
            req.qty = float(qty)
        elif notional is not None:
            req.notional = float(notional)
        if take_profit is not None or stop_loss is not None:
            req.order_class = OrderClass.BRACKET
            if take_profit is not None:
                req.take_profit = TakeProfitRequest(limit_price=take_profit)
            if stop_loss is not None:
                req.stop_loss = StopLossRequest(stop_price=stop_loss)
        order = self.trading.submit_order(order_data=req)
        return order.__dict__ if hasattr(order, "__dict__") else order

    def limit_order(self, symbol: str, side: str, qty: float, limit_price: float, tif: str="day") -> Dict[str, Any]:
        req = LimitOrderRequest(symbol=symbol, side=OrderSide.BUY if side.lower()=="buy" else OrderSide.SELL,
                                time_in_force=TimeInForce(tif), limit_price=float(limit_price), qty=float(qty))
        order = self.trading.submit_order(order_data=req)
        return order.__dict__ if hasattr(order, "__dict__") else order

    def cancel_all(self):
        return self.trading.cancel_orders()

    def get_positions(self):
        poss = self.trading.get_all_positions()
        res = []
        for p in poss:
            d = p.__dict__ if hasattr(p, "__dict__") else dict(p)
            res.append({k: str(v) for k,v in d.items()})
        return res

    def get_orders(self, status: Optional[str]=None, limit: Optional[int]=50):
        try:
            from alpaca.trading.requests import GetOrdersRequest
            req = GetOrdersRequest(status=status) if status else GetOrdersRequest()
            orders = self.trading.get_orders(req)
        except Exception:
            orders = self.trading.get_orders()
        out = []
        if isinstance(orders, list):
            it = orders[:limit]
        else:
            it = orders
        for o in it:
            d = o.__dict__ if hasattr(o, "__dict__") else dict(o)
            out.append({k: str(v) for k, v in d.items()})
        return out

    def get_recent_bars(self, symbols: List[str], timeframe: str="1Min", lookback_minutes: int=120) -> pd.DataFrame:
        tf_map = {"1Min": TimeFrame.Minute, "5Min": TimeFrame(5, "Min"), "15Min": TimeFrame(15, "Min"),
                  "Day": TimeFrame.Day}
        tf = tf_map.get(timeframe, TimeFrame.Minute)
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=lookback_minutes+5)
        req = StockBarsRequest(symbol_or_symbols=symbols, timeframe=tf, start=start, end=end)
        bars = self.data.get_stock_bars(req)
        df = bars.df if hasattr(bars, "df") else None
        if df is None:
            return pd.DataFrame()
        df = df.reset_index()
        return df
