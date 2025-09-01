# app/strategies/runner.py
import os
import json
import logging
import math
from typing import Dict, Any
from alpaca_client import AlpacaBroker
from config import Settings

logger = logging.getLogger("strategy")

def compute_qty_from_budget(price: float, budget: float, fractional: bool) -> float:
    """예산으로 수량 계산"""
    if price <= 0:
        return 0
    if fractional:
        return math.floor((budget / price) * 100) / 100.0
    return math.floor(budget / price)

class StrategyRunner:
    """자동매매 전략 실행"""
    
    def __init__(self, broker: AlpacaBroker, settings: Settings):
        self.broker = broker
        self.settings = settings
        self.running = False
        self.last_execution = {}
    
    def load_strategy(self, name: str) -> Dict[str, Any]:
        """전략 파일 로드"""
        filepath = os.path.join("config", "strategies", f"{name}.json")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"전략 파일을 찾을 수 없습니다: {name}")
        
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    
    async def tick(self):
        """주기적 실행"""
        if not self.settings.auto.enabled:
            return
        
        if self.running:
            logger.info("이전 작업이 진행중입니다. 건너뜁니다.")
            return
        
        self.running = True
        try:
            await self.run_once()
        except Exception as e:
            logger.error(f"전략 실행 오류: {e}")
        finally:
            self.running = False
    
    async def run_once(self):
        """전략 1회 실행"""
        if not self.settings.auto.strategy:
            logger.warning("전략이 선택되지 않았습니다")
            return
        
        try:
            strategy = self.load_strategy(self.settings.auto.strategy)
        except Exception as e:
            logger.error(f"전략 로드 실패: {e}")
            return
        
        if not strategy.get("enabled"):
            logger.info(f"전략 '{strategy['name']}'이 비활성화 상태입니다")
            return
        
        if not self.broker.enabled:
            logger.warning("Alpaca 연결이 없습니다")
            return
        
        logger.info(f"전략 '{strategy['name']}' 실행 시작")
        
        # 전략 타입별 실행
        strategy_type = strategy.get("type", "simple")
        
        if strategy_type == "simple":
            await self.execute_simple_strategy(strategy)
        elif strategy_type == "sma_crossover":
            await self.execute_sma_strategy(strategy)
        elif strategy_type == "rsi_reversion":
            await self.execute_rsi_strategy(strategy)
        elif strategy_type == "breakout":
            await self.execute_breakout_strategy(strategy)
        else:
            logger.warning(f"알 수 없는 전략 타입: {strategy_type}")
    
    async def execute_simple_strategy(self, strategy: Dict[str, Any]):
        """단순 매수 전략"""
        try:
            bp = self.broker.buying_power()
            if bp <= 0:
                logger.warning("매수력이 없습니다")
                return
            
            # 포지션 사이징
            sizing = strategy.get("position_sizing", {})
            sizing_type = sizing.get("type", "bp_percent")
            sizing_value = sizing.get("value", 1)
            
            total_budget = 0
            if sizing_type == "bp_percent":
                total_budget = bp * (sizing_value / 100.0)
            elif sizing_type == "fixed_notional":
                total_budget = sizing_value
            else:
                total_budget = bp * 0.01
            
            universe = strategy.get("universe", [])
            if not universe:
                logger.warning("유니버스가 비어있습니다")
                return
            
            # 균등 분할
            budget_per_symbol = total_budget / len(universe)
            
            for symbol in universe:
                try:
                    price = self.broker.latest_price(symbol)
                    if not price or price <= 0:
                        logger.warning(f"{symbol}: 가격 정보 없음")
                        continue
                    
                    qty = compute_qty_from_budget(
                        price, 
                        budget_per_symbol, 
                        self.settings.allow_fractional
                    )
                    
                    if qty <= 0:
                        continue
                    
                    order = self.broker.submit_order(
                        symbol, qty, "buy", "market"
                    )
                    
                    logger.info(
                        f"주문 제출: {symbol} {qty}주 @ ${price:.2f} "
                        f"(주문ID: {order.id})"
                    )
                    
                except Exception as e:
                    logger.error(f"{symbol} 주문 실패: {e}")
                    
        except Exception as e:
            logger.error(f"단순 전략 실행 오류: {e}")
    
    async def execute_sma_strategy(self, strategy: Dict[str, Any]):
        """SMA 크로스오버 전략 (플레이스홀더)"""
        # 실제 구현시 과거 가격 데이터를 가져와서
        # 이동평균선을 계산하고 교차 신호를 감지해야 함
        logger.info("SMA 크로스오버 전략 실행 (플레이스홀더)")
        await self.execute_simple_strategy(strategy)
    
    async def execute_rsi_strategy(self, strategy: Dict[str, Any]):
        """RSI 평균회귀 전략 (플레이스홀더)"""
        logger.info("RSI 평균회귀 전략 실행 (플레이스홀더)")
        await self.execute_simple_strategy(strategy)
    
    async def execute_breakout_strategy(self, strategy: Dict[str, Any]):
        """돌파 전략 (플레이스홀더)"""
        logger.info("돌파 전략 실행 (플레이스홀더)")
        await self.execute_simple_strategy(strategy)