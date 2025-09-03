"""
Strategy Runner - Optimized for Container Environment
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json
from .logging_system import log_trading, log_system, log_error

logger = logging.getLogger(__name__)

class StrategyRunner:
    """자동매매 전략 실행기 - 컨테이너 최적화"""
    
    def __init__(self, broker, config_manager, ws_manager, scheduler):
        self.broker = broker
        self.config_manager = config_manager
        self.ws_manager = ws_manager
        self.scheduler = scheduler
        
        self._enabled = False
        self._current_strategy = None
        self._job_id = "auto_trading_job"
    
    def get_status(self) -> Dict[str, Any]:
        """자동매매 상태 반환"""
        config = self.config_manager.get_auto_trading_config()
        
        next_run = None
        if self._enabled and self.scheduler:
            job = self.scheduler.get_job(self._job_id)
            if job and job.next_run_time:
                next_run = job.next_run_time.strftime("%H:%M:%S")
        
        return {
            "enabled": self._enabled,
            "strategy": config.get("strategy", "Simple_Buy"),
            "interval": config.get("interval_minutes", 1),
            "next_run": next_run
        }
    
    async def start_auto_trading(self):
        """자동매매 시작"""
        try:
            if self._enabled:
                logger.info(self.config_manager.get_message('auto_already_running'))
                return
            
            config = self.config_manager.get_auto_trading_config()
            strategy_name = config.get("strategy", "Simple_Buy")
            interval_minutes = config.get("interval_minutes", 1)
            
            # 전략 로드
            self._current_strategy = self._load_strategy(strategy_name)
            if not self._current_strategy:
                raise ValueError(self.config_manager.get_message('strategy_not_found', strategy=strategy_name))
            
            # 스케줄러에 작업 추가
            self.scheduler.add_job(
                func=self._execute_strategy,
                trigger="interval",
                minutes=interval_minutes,
                id=self._job_id,
                replace_existing=True,
                max_instances=1
            )
            
            self._enabled = True
            
            # 설정 업데이트
            self.config_manager.update_auto_trading_config({"enabled": True})
            
            logger.info(self.config_manager.get_message('auto_started', strategy=strategy_name, interval=interval_minutes))
            
            # WebSocket으로 상태 전송
            await self._broadcast_status()
            
        except Exception as e:
            logger.error(self.config_manager.get_message('auto_start_error', error=str(e)))
            raise
    
    async def stop_auto_trading(self):
        """자동매매 중지"""
        try:
            if not self._enabled:
                logger.info(self.config_manager.get_message('auto_already_stopped'))
                return
            
            # 스케줄러에서 작업 제거
            try:
                self.scheduler.remove_job(self._job_id)
            except:
                pass  # 작업이 없을 수 있음
            
            self._enabled = False
            self._current_strategy = None
            
            # 설정 업데이트
            self.config_manager.update_auto_trading_config({"enabled": False})
            
            logger.info(self.config_manager.get_message('auto_trading_shutdown'))
            
            # WebSocket으로 상태 전송
            await self._broadcast_status()
            
        except Exception as e:
            logger.error(self.config_manager.get_message('auto_trading_shutdown_failed', error=str(e)))
            raise
    
    def _load_strategy(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """전략 설정 로드"""
        try:
            strategies = self.config_manager.get_strategies_config()
            return strategies.get(strategy_name)
        except Exception as e:
            logger.error(self.config_manager.get_message('strategy_load_failed', error=str(e)))
            return None
    
    async def _execute_strategy(self):
        """전략 실행"""
        try:
            if not self._enabled or not self._current_strategy:
                return
            
            logger.info(self.config_manager.get_message('strategy_execution_started', strategy=self._current_strategy.get('name', 'Unknown')))
            
            # 계좌 정보 조회
            account_info = await self.broker.get_account_info()
            buying_power = account_info.get("buying_power", 0)
            
            if buying_power < 100:  # 최소 매수력 체크
                logger.warning(self.config_manager.get_message('insufficient_buying_power'))
                return
            
            # 전략별 실행 로직
            strategy_type = self._current_strategy.get("type", "simple_buy")
            
            if strategy_type == "simple_buy":
                await self._execute_simple_buy_strategy(buying_power)
            elif strategy_type == "sma_crossover":
                await self._execute_sma_strategy()
            else:
                logger.warning(self.config_manager.get_message('unsupported_strategy_type', strategy_type=strategy_type))
            
            logger.info(self.config_manager.get_message('strategy_execution_completed'))
            
        except Exception as e:
            logger.error(self.config_manager.get_message('strategy_execution_failed', error=str(e)))
    
    async def _execute_simple_buy_strategy(self, buying_power: float):
        """단순 매수 전략"""
        try:
            # myETFs.json에서 기본 ETF 구성 가져오기
            symbols = self._get_default_symbols()
            allocation_percent = self._current_strategy.get("allocation_percent", 30)
            
            # 전체 예산의 일정 비율 사용
            total_budget = buying_power * (allocation_percent / 100)
            budget_per_symbol = total_budget / len(symbols)
            
            logger.info(self.config_manager.get_message('simple_buy_strategy_info', total_budget=total_budget, budget_per_symbol=budget_per_symbol))
            
            for symbol in symbols:
                try:
                    # 현재 가격 조회
                    quote = await self.broker.get_quote(symbol)
                    if not quote:
                        logger.warning(self.config_manager.get_message('quote_fetch_failed', symbol=symbol))
                        continue
                    
                    current_price = (quote["bid"] + quote["ask"]) / 2
                    qty = int(budget_per_symbol / current_price)
                    
                    if qty > 0:
                        # 시장가 매수 주문
                        order_id = await self.broker.submit_order(
                            symbol=symbol,
                            qty=qty,
                            side="buy",
                            order_type="market"
                        )
                        
                        logger.info(self.config_manager.get_message('order_submitted', symbol=symbol, qty=qty, order_id=order_id))
                        
                        # 짧은 지연 (너무 빠른 주문 방지)
                        await asyncio.sleep(1)
                
                except Exception as e:
                    logger.error(self.config_manager.get_message('symbol_order_failed', symbol=symbol, error=str(e)))
                    continue
                    
        except Exception as e:
            logger.error(self.config_manager.get_message('simple_buy_strategy_failed', error=str(e)))
    
    async def _execute_sma_strategy(self):
        """SMA 크로스오버 전략 (간단 버전)"""
        try:
            # 실제 구현에서는 기술적 분석 로직 추가
            logger.info(self.config_manager.get_message('sma_strategy_execution'))
            
        except Exception as e:
            logger.error(self.config_manager.get_message('sma_strategy_failed', error=str(e)))
    
    def _get_default_symbols(self) -> list:
        """myETFs.json에서 기본 ETF 구성 가져오기"""
        try:
            # 전략에서 지정된 symbols가 있으면 우선 사용
            if "symbols" in self._current_strategy:
                return self._current_strategy["symbols"]
            
            # myETFs.json에서 기본 ETF 구성 로드
            import json
            etf_file = self.config_manager.config_dir / "myETFs.json"
            
            if etf_file.exists():
                with open(etf_file, 'r', encoding='utf-8') as f:
                    etf_data = json.load(f)
                
                # CONSERVATIVE_MIX ETF를 기본값으로 사용
                conservative_etf = etf_data.get('custom_etfs', {}).get('CONSERVATIVE_MIX')
                if conservative_etf and 'components' in conservative_etf:
                    return [component['symbol'] for component in conservative_etf['components']]
            
            # myETFs.json이 없거나 오류가 있을 경우 하드코딩된 기본값 사용
            logger.warning(self.config_manager.get_message('etf_config_load_warning'))
            return ["VOO", "VTI", "QQQ"]
            
        except Exception as e:
            logger.error(self.config_manager.get_message('etf_config_load_failed', error=str(e)))
            return ["VOO", "VTI", "QQQ"]
    
    async def _broadcast_status(self):
        """상태 변경을 WebSocket으로 브로드캐스트"""
        try:
            status = self.get_status()
            await self.ws_manager.broadcast({
                "type": "auto_trading_status",
                "payload": status
            })
        except Exception as e:
            logger.error(self.config_manager.get_message('status_broadcast_failed', error=str(e)))