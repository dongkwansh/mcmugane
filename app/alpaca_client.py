# app/alpaca_client.py
from typing import Optional
from config import Settings
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
# [수정] 'LatestTradeRequest' 대신 'StockLatestTradeRequest'를 직접 임포트합니다.
from alpaca.data.requests import StockLatestTradeRequest 

class AlpacaBroker:
    """Alpaca API와의 모든 통신을 담당하는 클래스입니다."""
    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = bool(settings.alpaca.get("key_id") and settings.alpaca.get("secret_key"))
        self.trading = None
        self.data = None
        if self.enabled:
            self.trading = TradingClient(
                api_key=settings.alpaca["key_id"],
                secret_key=settings.alpaca["secret_key"],
                paper=(settings.mode == "PAPER")
            )
            self.data = StockHistoricalDataClient(
                settings.alpaca["key_id"], 
                settings.alpaca["secret_key"]
            )

    def _require(self):
        """API 사용 전 인증 정보를 확인합니다."""
        if not self.enabled:
            raise RuntimeError("Alpaca 인증 정보가 없습니다. .env 파일에 키를 설정하세요.")

    def latest_price(self, symbol: str) -> Optional[float]:
        """특정 심볼의 최신 체결가를 가져옵니다."""
        if not self.enabled: return None
        try:
            # [수정] 버전에 맞는 StockLatestTradeRequest를 사용합니다.
            req = StockLatestTradeRequest(symbol_or_symbols=symbol)
            trade = self.data.get_stock_latest_trade(req)
            # API 응답이 딕셔너리 형태일 경우 심볼 키로 접근
            if isinstance(trade, dict):
                trade = trade.get(symbol)
            return float(trade.price) if trade and hasattr(trade, "price") else None
        except Exception as e:
            logging.getLogger("alpaca").error(f"{symbol} 가격 조회 실패: {e}")
            return None # 오류 발생 시 None 반환
            
    # --- account, buying_power, positions, get_open_orders, cancel_order, submit_order 함수는 이전과 동일 ---
    def account(self):
        self._require()
        return self.trading.get_account()

    def buying_power(self) -> float:
        if not self.enabled: return 0.0
        return float(self.account().buying_power)

    def positions(self):
        if not self.enabled: return []
        return self.trading.get_all_positions()

    def get_open_orders(self):
        if not self.enabled: return []
        return self.trading.get_orders(GetOrdersRequest(status="open"))

    def cancel_order(self, oid: str):
        self._require()
        return self.trading.cancel_order_by_id(oid)

    def submit_order(self, symbol: str, qty: float, side: str, order_type: str, limit_price: Optional[float]=None):
        self._require()
        side_enum = OrderSide.BUY if side.lower()=="buy" else OrderSide.SELL
        tif = TimeInForce.DAY
        if order_type.lower() == "market":
            req = MarketOrderRequest(symbol=symbol, qty=qty, side=side_enum, time_in_force=tif)
        else:
            req = LimitOrderRequest(symbol=symbol, qty=qty, side=side_enum, time_in_force=tif, limit_price=limit_price)
        return self.trading.submit_order(req)