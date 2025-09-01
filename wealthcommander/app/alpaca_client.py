# app/alpaca_client.py
import logging
from typing import Optional
from config import Settings
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.requests import StockLatestTradeRequest

logger = logging.getLogger("alpaca")

class AlpacaBroker:
    """Alpaca API 클라이언트"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = bool(
            settings.alpaca.get("key_id") and 
            settings.alpaca.get("secret_key")
        )
        self.trading = None
        self.data = None
        
        if self.enabled:
            try:
                self.trading = TradingClient(
                    api_key=settings.alpaca["key_id"],
                    secret_key=settings.alpaca["secret_key"],
                    paper=(settings.mode == "PAPER")
                )
                self.data = StockHistoricalDataClient(
                    settings.alpaca["key_id"],
                    settings.alpaca["secret_key"]
                )
                logger.info(f"Alpaca 클라이언트 초기화 성공 (모드: {settings.mode})")
            except Exception as e:
                logger.error(f"Alpaca 클라이언트 초기화 실패: {e}")
                self.enabled = False

    def _require(self):
        """API 사용 전 인증 확인"""
        if not self.enabled:
            raise RuntimeError("Alpaca 인증 정보가 없습니다.")

    def latest_price(self, symbol: str) -> Optional[float]:
        """현재가 조회"""
        if not self.enabled:
            return None
        try:
            req = StockLatestTradeRequest(symbol_or_symbols=symbol)
            trade = self.data.get_stock_latest_trade(req)
            if isinstance(trade, dict):
                trade = trade.get(symbol)
            return float(trade.price) if trade and hasattr(trade, "price") else None
        except Exception as e:
            logger.error(f"{symbol} 가격 조회 실패: {e}")
            return None

    def account(self):
        """계좌 정보 조회"""
        self._require()
        return self.trading.get_account()

    def buying_power(self) -> float:
        """매수력 조회"""
        if not self.enabled:
            return 0.0
        try:
            return float(self.account().buying_power)
        except Exception as e:
            logger.error(f"매수력 조회 실패: {e}")
            return 0.0

    def positions(self):
        """포지션 조회"""
        if not self.enabled:
            return []
        try:
            return self.trading.get_all_positions()
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []

    def get_open_orders(self):
        """미체결 주문 조회"""
        if not self.enabled:
            return []
        try:
            return self.trading.get_orders(GetOrdersRequest(status="open"))
        except Exception as e:
            logger.error(f"주문 조회 실패: {e}")
            return []

    def cancel_order(self, oid: str):
        """주문 취소"""
        self._require()
        return self.trading.cancel_order_by_id(oid)

    def submit_order(self, symbol: str, qty: float, side: str, 
                    order_type: str, limit_price: Optional[float] = None):
        """주문 제출"""
        self._require()
        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        tif = TimeInForce.DAY
        
        if order_type.lower() == "market":
            req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                time_in_force=tif
            )
        else:
            req = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                time_in_force=tif,
                limit_price=limit_price
            )
        
        return self.trading.submit_order(req)