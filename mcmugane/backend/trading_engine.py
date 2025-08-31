import json
import time
from datetime import datetime
import threading
from typing import Dict, Any, List
import schedule

class TradingEngine:
    def __init__(self, alpaca_client, db_manager, config_path='/app/config'):
        self.alpaca = alpaca_client
        self.db = db_manager
        self.config_path = config_path
        self.strategies = {}
        self.is_running = False
        self.load_strategies()
        
    def load_strategies(self):
        """전략 파일들 로드"""
        strategy_files = ['ma_crossover.json', 'rsi_strategy.json', 'dca_strategy.json']
        
        for file in strategy_files:
            with open(f'{self.config_path}/{file}', 'r') as f:
                strategy_config = json.load(f)
                if strategy_config.get('enabled'):
                    self.strategies[strategy_config['name']] = strategy_config
    
    def start_auto_trading(self):
        """자동매매 시작"""
        self.is_running = True
        self.setup_schedules()
        
        # 별도 스레드에서 실행
        thread = threading.Thread(target=self._run_scheduler)
        thread.daemon = True
        thread.start()
        
        self.db.add_log('INFO', 'SYSTEM', '자동매매 시작됨')
    
    def stop_auto_trading(self):
        """자동매매 중지"""
        self.is_running = False
        schedule.clear()
        self.db.add_log('INFO', 'SYSTEM', '자동매매 중지됨')
    
    def setup_schedules(self):
        """스케줄 설정"""
        for name, strategy in self.strategies.items():
            if strategy.get('schedule'):
                interval = strategy['schedule'].get('checkInterval', 300)
                schedule.every(interval).seconds.do(
                    self.execute_strategy, strategy_name=name
                )
    
    def _run_scheduler(self):
        """스케줄러 실행"""
        while self.is_running:
            schedule.run_pending()
            time.sleep(1)
    
    def execute_strategy(self, strategy_name: str):
        """전략 실행"""
        strategy = self.strategies.get(strategy_name)
        if not strategy:
            return
        
        try:
            if 'MA Crossover' in strategy_name:
                self.execute_ma_crossover(strategy)
            elif 'RSI' in strategy_name:
                self.execute_rsi_strategy(strategy)
            elif 'Dollar Cost' in strategy_name:
                self.execute_dca_strategy(strategy)
        except Exception as e:
            self.db.add_log('ERROR', 'STRATEGY', f'{strategy_name} 실행 오류: {str(e)}')
    
    def execute_ma_crossover(self, strategy: Dict[str, Any]):
        """이동평균 교차 전략 실행"""
        params = strategy['parameters']
        positions = self.alpaca.get_positions()
        
        # 보유 종목들에 대해 매도 신호 확인
        for position in positions:
            symbol = position['symbol']
            bars = self.alpaca.get_bars(symbol, params['timeframe'], limit=params['longPeriod'] + 1)
            
            if len(bars) < params['longPeriod']:
                continue
            
            short_ma = bars['close'].rolling(window=params['shortPeriod']).mean()
            long_ma = bars['close'].rolling(window=params['longPeriod']).mean()
            
            # 데드크로스 - 매도
            if short_ma.iloc[-2] > long_ma.iloc[-2] and short_ma.iloc[-1] < long_ma.iloc[-1]:
                self.alpaca.place_order(
                    symbol=symbol,
                    qty=position['qty'],
                    side='sell',
                    order_type='market'
                )
                self.db.add_log('INFO', 'TRADE', f'MA Crossover 매도: {symbol}')
    
    def execute_rsi_strategy(self, strategy: Dict[str, Any]):
        """RSI 전략 실행"""
        params = strategy['parameters']
        
        # 관심 종목 리스트 (설정 파일에서 로드 가능)
        watchlist = ['SPY', 'QQQ', 'AAPL', 'MSFT']
        
        for symbol in watchlist:
            bars = self.alpaca.get_bars(symbol, params['timeframe'], limit=params['rsiPeriod'] + 1)
            
            if len(bars) < params['rsiPeriod']:
                continue
            
            # RSI 계산
            rsi = self.calculate_rsi(bars['close'], params['rsiPeriod'])
            
            if rsi < params['oversoldLevel']:
                # 과매도 - 매수 신호
                buying_power = self.alpaca.get_buying_power()
                max_position = buying_power * strategy['allocation']['maxPositionSize']
                current_price = self.alpaca.get_current_price(symbol)
                qty = int(max_position / current_price)
                
                if qty > 0:
                    self.alpaca.place_order(
                        symbol=symbol,
                        qty=qty,
                        side='buy',
                        order_type='market'
                    )
                    self.db.add_log('INFO', 'TRADE', f'RSI 매수: {symbol} (RSI: {rsi:.2f})')
    
    def execute_dca_strategy(self, strategy: Dict[str, Any]):
        """적립식 투자 전략 실행"""
        params = strategy['parameters']
        amount_per_trade = params['amountPerTrade']
        
        for symbol in params['targetTickers']:
            current_price = self.alpaca.get_current_price(symbol)
            qty = int(amount_per_trade / current_price)
            
            if qty > 0:
                self.alpaca.place_order(
                    symbol=symbol,
                    qty=qty,
                    side='buy',
                    order_type='market'
                )
                self.db.add_log('INFO', 'TRADE', f'DCA 매수: {symbol} {qty}주')
    
    def calculate_rsi(self, prices, period: int) -> float:
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1]