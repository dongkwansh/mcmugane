import alpaca_trade_api as tradeapi
from typing import Optional, Dict, Any, List
import pandas as pd
from datetime import datetime, timedelta

class AlpacaClient:
    def __init__(self, api_key: str, secret_key: str, base_url: str):
        self.api = tradeapi.REST(
            api_key,
            secret_key,
            base_url,
            api_version='v2'
        )
        
    def get_account(self) -> Dict[str, Any]:
        """계좌 정보 조회"""
        account = self.api.get_account()
        return {
            'buying_power': float(account.buying_power),
            'portfolio_value': float(account.portfolio_value),
            'cash': float(account.cash),
            'day_trade_count': account.daytrade_count,
            'pattern_day_trader': account.pattern_day_trader
        }
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """보유 포지션 조회"""
        positions = self.api.list_positions()
        return [{
            'symbol': pos.symbol,
            'qty': float(pos.qty),
            'avg_entry_price': float(pos.avg_entry_price),
            'market_value': float(pos.market_value),
            'cost_basis': float(pos.cost_basis),
            'unrealized_pl': float(pos.unrealized_pl),
            'unrealized_plpc': float(pos.unrealized_plpc),
            'current_price': float(pos.current_price)
        } for pos in positions]
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """특정 종목 포지션 조회"""
        try:
            pos = self.api.get_position(symbol)
            return {
                'symbol': pos.symbol,
                'qty': float(pos.qty),
                'avg_entry_price': float(pos.avg_entry_price),
                'market_value': float(pos.market_value),
                'current_price': float(pos.current_price)
            }
        except:
            return None
    
    def get_buying_power(self) -> float:
        """구매력 조회"""
        account = self.api.get_account()
        return float(account.buying_power)
    
    def get_current_price(self, symbol: str) -> float:
        """현재가 조회"""
        quote = self.api.get_latest_quote(symbol)
        return float(quote.ask_price)
    
    def place_order(self, 
                   symbol: str, 
                   qty: int, 
                   side: str, 
                   order_type: str = 'market',
                   limit_price: Optional[float] = None,
                   stop_price: Optional[float] = None,
                   time_in_force: str = 'day') -> Dict[str, Any]:
        """주문 실행"""
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type=order_type,
                time_in_force=time_in_force,
                limit_price=limit_price,
                stop_price=stop_price
            )
            return {
                'success': True,
                'order_id': order.id,
                'symbol': order.symbol,
                'qty': order.qty,
                'side': order.side,
                'type': order.type,
                'status': order.status
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """주문 취소"""
        try:
            self.api.cancel_order(order_id)
            return {'success': True, 'message': f'주문 {order_id} 취소됨'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_orders(self, status: str = 'open') -> List[Dict[str, Any]]:
        """주문 목록 조회"""
        orders = self.api.list_orders(status=status)
        return [{
            'id': order.id,
            'symbol': order.symbol,
            'qty': order.qty,
            'side': order.side,
            'type': order.type,
            'limit_price': order.limit_price,
            'status': order.status,
            'created_at': order.created_at,
            'filled_qty': order.filled_qty
        } for order in orders]
    
    def get_bars(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """가격 데이터 조회"""
        bars = self.api.get_bars(
            symbol,
            timeframe,
            limit=limit
        ).df
        return bars
    
    def get_portfolio_history(self, period: str = '1D') -> Dict[str, Any]:
        """포트폴리오 히스토리 조회"""
        history = self.api.get_portfolio_history(period=period)
        return {
            'timestamp': history.timestamp,
            'equity': history.equity,
            'profit_loss': history.profit_loss,
            'profit_loss_pct': history.profit_loss_pct
        }