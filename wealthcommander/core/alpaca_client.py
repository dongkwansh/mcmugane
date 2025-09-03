"""
Alpaca Trading Client - Optimized for Container Environment
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import pytz

# Alpaca imports
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.common.exceptions import APIError
from .logging_system import log_trading, log_error, log_system

logger = logging.getLogger(__name__)
trading_logger = logging.getLogger('trading')

class AlpacaBroker:
    """Alpaca 브로커 클라이언트 - 컨테이너 최적화"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.trading_client = None
        self.data_client = None
        self._initialized = False
        self._demo_mode = False
        
    async def initialize(self):
        """브로커 클라이언트 초기화"""
        try:
            account_config = self.config_manager.get_account_config()
            account_name = self.config_manager.get_current_account()
            
            key_id = account_config.get("key_id")
            secret_key = account_config.get("secret_key")
            is_paper = account_config.get("type", "PAPER") == "PAPER"
            
            if not key_id or not secret_key:
                logger.warning(self.config_manager.get_message('alpaca_init_warning'))
                trading_logger.warning(f"계좌 {account_name}: API 키가 없어 데모 모드로 실행")
                self._demo_mode = True
                self._initialized = True
                return
            
            trading_logger.info(f"계좌 초기화 시작: {account_name} ({'모의거래' if is_paper else '실제거래'})")
            
            # Trading client 초기화
            self.trading_client = TradingClient(
                api_key=key_id,
                secret_key=secret_key,
                paper=is_paper
            )
            
            # Data client 초기화 (무료 데이터 사용)
            self.data_client = StockHistoricalDataClient(
                api_key=key_id,
                secret_key=secret_key
            )
            
            # 연결 테스트
            account = self.trading_client.get_account()
            logger.info(self.config_manager.get_message('alpaca_connected', account=account.account_number, mode='PAPER' if is_paper else 'LIVE'))
            
            self._demo_mode = False
            self._initialized = True
            
        except Exception as e:
            logger.error(self.config_manager.get_message('alpaca_init_failed', error=str(e)))
            logger.warning(self.config_manager.get_message('demo_mode_switch'))
            self._demo_mode = True
            self._initialized = True
    
    def _ensure_initialized(self):
        """초기화 확인"""
        if not self._initialized:
            raise RuntimeError(self.config_manager.get_message('alpaca_client_not_initialized'))
    
    async def get_account_info(self) -> Dict[str, Any]:
        """계좌 정보 조회"""
        self._ensure_initialized()
        
        if self._demo_mode:
            return {
                "account_number": "DEMO-ACCOUNT",
                "status": "ACTIVE",
                "equity": 100000.00,
                "buying_power": 100000.00,
                "cash": 100000.00,
                "portfolio_value": 100000.00,
                "day_trade_count": 0,
                "pattern_day_trader": False
            }
        
        try:
            account = self.trading_client.get_account()
            
            return {
                "account_number": account.account_number,
                "status": account.status.value,
                "equity": float(account.equity),
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "day_trade_count": account.day_trade_count,
                "pattern_day_trader": account.pattern_day_trader
            }
            
        except Exception as e:
            logger.error(self.config_manager.get_message('account_info_failed', error=str(e)))
            return {}
    
    async def get_market_status(self) -> Dict[str, Any]:
        """시장 상태 조회"""
        self._ensure_initialized()
        
        if self._demo_mode:
            # 데모 모드에서는 시간에 따라 시장 상태 시뮬레이션
            import datetime
            now = datetime.datetime.now()
            is_weekday = now.weekday() < 5
            is_market_hours = 9 <= now.hour < 16
            is_open = is_weekday and is_market_hours
            
            return {
                "is_open": is_open,
                "next_open": None,
                "next_close": None,
                "timestamp": now.isoformat()
            }
        
        try:
            clock = self.trading_client.get_clock()
            
            return {
                "is_open": clock.is_open,
                "next_open": clock.next_open.isoformat() if clock.next_open else None,
                "next_close": clock.next_close.isoformat() if clock.next_close else None,
                "timestamp": clock.timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(self.config_manager.get_message('market_status_query_failed', error=str(e)))
            return {"is_open": False}
    
    def get_market_time(self) -> datetime:
        """현재 시장 시간 반환"""
        ny_tz = pytz.timezone('America/New_York')
        return datetime.now(ny_tz)
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """포지션 조회"""
        self._ensure_initialized()
        
        try:
            positions = self.trading_client.get_all_positions()
            
            result = []
            for pos in positions:
                result.append({
                    "symbol": pos.symbol,
                    "qty": float(pos.qty),
                    "market_value": float(pos.market_value),
                    "cost_basis": float(pos.cost_basis),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_plpc": float(pos.unrealized_plpc),
                    "side": pos.side.value
                })
            
            return result
            
        except Exception as e:
            logger.error(self.config_manager.get_message('positions_query_failed', error=str(e)))
            return []
    
    async def get_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """주문 내역 조회"""
        self._ensure_initialized()
        
        try:
            orders = self.trading_client.get_orders()
            
            result = []
            for order in orders[:limit]:
                result.append({
                    "id": order.id,
                    "symbol": order.symbol,
                    "qty": float(order.qty),
                    "side": order.side.value,
                    "order_type": order.order_type.value,
                    "status": order.status.value,
                    "limit_price": float(order.limit_price) if order.limit_price else None,
                    "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                    "created_at": order.created_at.isoformat() if order.created_at else None
                })
            
            return result
            
        except Exception as e:
            logger.error(self.config_manager.get_message('orders_query_failed', error=str(e)))
            return []
    
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """종목 시세 조회"""
        self._ensure_initialized()
        
        if self._demo_mode:
            # 데모 모드에서는 가상 시세 반환
            return self._get_demo_quote(symbol)
        
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
            quotes = self.data_client.get_stock_latest_quote(request)
            
            if symbol in quotes:
                quote = quotes[symbol]
                return {
                    "symbol": symbol,
                    "bid": float(quote.bid_price),
                    "ask": float(quote.ask_price),
                    "timestamp": quote.timestamp.isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.error(self.config_manager.get_message('quote_query_failed', symbol=symbol, error=str(e)))
            return None
    
    def _get_demo_quote(self, symbol: str) -> Dict[str, Any]:
        """데모 모드용 가상 시세 생성"""
        import random
        from datetime import datetime
        
        # 주요 종목별 기본 가격 설정
        base_prices = {
            'AAPL': 185.0,
            'MSFT': 420.0,
            'GOOGL': 145.0,
            'AMZN': 155.0,
            'TSLA': 250.0,
            'NVDA': 875.0,
            'VOO': 450.0,
            'VTI': 270.0,
            'QQQ': 480.0,
            'BND': 75.0,
            'VNQ': 95.0,
            'SOXL': 35.0
        }
        
        # 기본 가격이 없는 경우 랜덤 생성
        base_price = base_prices.get(symbol, random.uniform(50, 200))
        
        # 스프레드 생성 (0.1% ~ 0.5%)
        spread_percent = random.uniform(0.001, 0.005)
        spread = base_price * spread_percent
        
        bid_price = base_price - (spread / 2)
        ask_price = base_price + (spread / 2)
        
        return {
            "symbol": symbol,
            "bid": round(bid_price, 2),
            "ask": round(ask_price, 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def submit_order(self, symbol: str, qty: float, side: str, 
                          order_type: str = "market", limit_price: Optional[float] = None) -> Optional[str]:
        """주문 제출"""
        self._ensure_initialized()
        
        if self._demo_mode:
            # 데모 모드에서는 가상 주문 ID 반환
            import uuid
            demo_order_id = f"DEMO-{uuid.uuid4().hex[:8]}"
            logger.info(self.config_manager.get_message('demo_order_submitted', symbol=symbol, qty=qty, side=side, order_id=demo_order_id))
            return demo_order_id
        
        try:
            side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            
            if order_type.lower() == "market":
                request = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side_enum,
                    time_in_force=TimeInForce.DAY
                )
            else:
                if not limit_price:
                    raise ValueError(self.config_manager.get_message('limit_order_price_required'))
                
                request = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side_enum,
                    time_in_force=TimeInForce.DAY,
                    limit_price=limit_price
                )
            
            order = self.trading_client.submit_order(request)
            logger.info(self.config_manager.get_message('order_submit_success', order_id=order.id))
            
            return order.id
            
        except APIError as e:
            error_msg = str(e)
            
            # 한국어 오류 메시지 변환
            if "insufficient" in error_msg.lower():
                if "buying power" in error_msg.lower():
                    raise Exception(self.config_manager.get_message('insufficient_funds'))
                elif "shares" in error_msg.lower() or "qty" in error_msg.lower():
                    raise Exception(self.config_manager.get_message('insufficient_shares'))
            elif "market" in error_msg.lower() and "closed" in error_msg.lower():
                raise Exception(self.config_manager.get_message('market_closed'))
            elif "symbol" in error_msg.lower() and "invalid" in error_msg.lower():
                raise Exception(self.config_manager.get_message('invalid_symbol', symbol=symbol))
            else:
                raise Exception(self.config_manager.get_message('order_processing_error', error=error_msg))
                
        except Exception as e:
            logger.error(self.config_manager.get_message('order_submit_failed', error=str(e)))
            raise
    
    async def cancel_order(self, order_id: str) -> bool:
        """주문 취소"""
        self._ensure_initialized()
        
        try:
            self.trading_client.cancel_order_by_id(order_id)
            logger.info(self.config_manager.get_message('order_cancel_success', order_id=order_id))
            return True
            
        except Exception as e:
            logger.error(self.config_manager.get_message('order_cancel_failed', error=str(e)))
            return False
    
    async def cancel_all_orders(self) -> int:
        """모든 주문 취소"""
        self._ensure_initialized()
        
        try:
            cancelled_orders = self.trading_client.cancel_orders()
            count = len(cancelled_orders)
            logger.info(self.config_manager.get_message('bulk_orders_cancelled', count=count))
            return count
            
        except Exception as e:
            logger.error(self.config_manager.get_message('bulk_cancel_failed', error=str(e)))
            return 0