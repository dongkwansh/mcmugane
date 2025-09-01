# app/strategies/runner.py
import os
import json
import logging
import math
from alpaca_client import AlpacaBroker
from config import Settings

LOG = logging.getLogger("auto")

def compute_qty_from_budget(price: float, budget: float, fractional: bool) -> float:
    """예산과 가격을 바탕으로 주문 수량을 계산합니다."""
    if price <= 0: return 0
    if fractional:
        # 소수점 둘째 자리까지 내림하여 계산
        return math.floor((budget / price) * 100) / 100.0
    return math.floor(budget / price)

class StrategyRunner:
    """선택된 자동매매 전략을 주기적으로 실행하는 클래스."""
    def __init__(self, broker: AlpacaBroker, settings: Settings):
        self.broker = broker
        self.settings = settings
        self.running = False # 중복 실행 방지 플래그

    def load_strategy(self, name: str):
        """전략 설정 파일을 로드합니다."""
        filepath = os.path.join("config", "strategies", name + ".json")
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    async def run_once(self):
        """전략을 1회 실행합니다."""
        if not self.settings.auto.strategy:
            LOG.warning("자동매매 전략이 선택되지 않았습니다.")
            return

        try:
            strat = self.load_strategy(self.settings.auto.strategy)
        except FileNotFoundError:
            LOG.error(f"전략 파일을 찾을 수 없습니다: {self.settings.auto.strategy}.json")
            return

        # 전략 파일 내에서 'enabled'가 false이면 실행하지 않음
        if not strat.get("enabled"):
            return

        if not self.broker.enabled:
            LOG.warning("Alpaca 인증 정보가 없어 자동매매를 건너뜁니다.")
            return

        # --- 중요: 이 부분은 실제 매매 신호를 생성하는 로직이 아닙니다. ---
        # 현재는 설정된 예산에 맞춰 매수만 수행하는 플레이스홀더(placeholder)입니다.
        # 실제 투자 전략(예: 이동평균선 교차 시 매수)은 이 부분에 직접 구현해야 합니다.
        LOG.info(f"전략 '{strat['name']}'에 대한 플레이스홀더 매수를 실행합니다.")

        try:
            bp = self.broker.buying_power()
            if bp <= 0:
                LOG.warning("매수력이 0이므로 거래를 실행할 수 없습니다.")
                return
        except Exception as e:
            LOG.error(f"매수력 조회 실패: {e}")
            return

        # 전략 설정 파일에서 포지션 사이징(매수 규모) 결정
        sizing = strat.get("position_sizing", {})
        sizing_type = sizing.get("type", "bp_percent")
        sizing_value = sizing.get("value", 1) 

        total_budget = 0
        if sizing_type == "bp_percent":
            total_budget = bp * (sizing_value / 100.0)
        elif sizing_type == "fixed_notional":
            total_budget = sizing_value
        else:
            LOG.warning(f"알 수 없는 포지션 사이징 타입: {sizing_type}. 기본값(1% BP)을 사용합니다.")
            total_budget = bp * 0.01

        universe = strat.get("universe", [])
        if not universe:
            LOG.warning(f"전략 '{strat['name']}'의 유니버스(대상 종목)가 비어있습니다.")
            return

        # 전체 예산을 유니버스 내 모든 종목에 균등하게 배분
        budget_per_symbol = total_budget / len(universe)

        for sym in universe:
            try:
                price = self.broker.latest_price(sym)
                if price is None or price <= 0:
                    LOG.warning(f"{sym}의 유효한 가격을 가져올 수 없습니다.")
                    continue

                qty = compute_qty_from_budget(price, budget_per_symbol, self.settings.allow_fractional)

                if qty <= 0: continue

                o = self.broker.submit_order(sym, qty, "buy", "market")
                log_event = {
                    "event": "order_submitted", "mode": self.settings.mode,
                    "symbol": sym, "qty": qty, "side": "buy", "order_type": "market",
                    "auto": True, "strategy": strat['name'], "order_id": o.id
                }
                LOG.info(json.dumps(log_event, ensure_ascii=False))

            except Exception as e:
                LOG.error(f"'{sym}' 자동 주문 실패: {e}")

    async def tick(self):
        """스케줄러에 의해 주기적으로 호출되는 함수."""
        if not self.settings.auto.enabled: return
        if self.running:
            LOG.info("이전 자동매매 작업이 아직 실행 중이므로 이번 틱은 건너뜁니다.")
            return

        self.running = True
        try:
            await self.run_once()
        except Exception as e:
            LOG.error(f"자동매매 틱 실행 중 예외 발생: {e}", exc_info=True)
        finally:
            self.running = False