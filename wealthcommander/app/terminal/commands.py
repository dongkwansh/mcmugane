# app/terminal/commands.py

import json
import logging
import os
from typing import Dict, Any, Callable, Awaitable
from app.alpaca_client import AlpacaBroker
from app.config import save_settings, Settings, get_market_status
# core.utils에서 공용 함수 임포트
from app.core.utils import (compute_qty_from_budget, format_number, 
                            format_order, format_position)

logger = logging.getLogger("terminal")

class TerminalLogic:
    """Handles the logic for terminal commands."""
    def __init__(self, broker: AlpacaBroker, settings: Settings, scheduler=None, runner=None,
                 on_state_change: Callable[[], Awaitable[None]] = None):
        self.br = broker
        self.settings = settings
        self.scheduler = scheduler
        self.runner = runner
        self.on_state_change = on_state_change

    async def _trigger_state_change(self):
        if self.on_state_change:
            await self.on_state_change()

    def _append_log(self, event_data: dict):
        # Using logger.info with a structured dictionary
        logger.info(json.dumps(event_data, ensure_ascii=False))

    async def handle(self, d: Dict[str, Any]) -> str:
        """Main handler to dispatch commands."""
        cmd = d.get("cmd")
        
        handlers = {
            "HELP": self.cmd_help, "STATUS": self.cmd_status,
            "PORTFOLIO": self.cmd_portfolio, "POSITIONS": self.cmd_portfolio,
            "BALANCE": self.cmd_balance, "ORDERS": self.cmd_orders,
            "INFO": self.cmd_info, "AUTO": self.cmd_auto,
            "STRATEGY": self.cmd_strategy, "INTERVAL": self.cmd_interval,
            "BUY": self.cmd_trade, "SELL": self.cmd_trade,
            "CANCEL": self.cmd_cancel
        }

        handler = handlers.get(cmd)
        if handler:
            # Pass the whole dictionary `d` to the handler
            return await handler(d)
        
        return f"알 수 없는 명령어: '{d.get('raw', cmd)}'"

    async def cmd_help(self, d: Dict) -> str:
        return """
╔══════════════════════════════════════════════════════════════╗
║                    WealthCommander 터미널 명령어               ║
╠══════════════════════════════════════════════════════════════╣
║ 기본: HELP, STATUS, CLEAR                                    ║
║ 계좌: PORTFOLIO, POSITIONS, BALANCE, ORDERS, HISTORY         ║
║ 조회: .{TICKER} (예: .AAPL)                                   ║
║ 매매: BUY/SELL .{TICKER} [수량/$금액/%], CANCEL {ID}           ║
║ 자동매매: AUTO {ON|OFF}, STRATEGY {이름}, INTERVAL {초}        ║
╚══════════════════════════════════════════════════════════════╝
"""
    
    async def cmd_status(self, d: Dict) -> str:
        market = get_market_status()
        job = self.scheduler.get_job('auto_trade') if self.scheduler else None
        is_paused = job.next_run_time is None if job else True

        status_lines = [
            "=" * 50, "시스템 상태", "=" * 50,
            f"현재 계정    : {self.settings.current_account} ({self.settings.mode})",
            f"Alpaca 연결  : {'연결됨' if self.br.enabled else '연결 안됨'}",
            f"매수력       : ${format_number(self.br.buying_power()) if self.br.enabled else 'N/A'}",
            f"자동매매     : {'ON' if self.settings.auto.enabled and not is_paused else 'OFF'}",
            f"활성 전략    : {self.settings.auto.strategy or '없음'}",
            f"실행 간격    : {self.settings.auto.interval_seconds}초",
            f"시장 상태    : {market['status']} ({market['ny_time']})",
        ]
        if not market['is_open']:
            status_lines.append(f"다음 개장    : {market['next_open']}")
        return "\n".join(status_lines)

    async def cmd_portfolio(self, d: Dict) -> str:
        try:
            positions = self.br.positions()
            if not positions: return "보유 포지션이 없습니다."
            
            total_value = sum(float(p.market_value) for p in positions)
            total_cost = sum(float(p.cost_basis) for p in positions)
            total_pnl = total_value - total_cost
            total_pnl_pct = (total_pnl / total_cost * 100) if total_cost != 0 else 0
            
            lines = [format_position(p) for p in positions]
            lines.append("=" * 80)
            lines.append(f"총 평가액: ${format_number(total_value)} | 총 손익: ${format_number(total_pnl)} ({total_pnl_pct:+.2f}%)")
            return "\n".join(lines)
        except Exception as e:
            return f"포트폴리오 조회 실패: {e}"

    async def cmd_balance(self, d: Dict) -> str:
        try:
            acc = self.br.account()
            return (f"{'='*50}\n계좌 정보\n{'='*50}\n"
                    f"계좌 가치    : ${format_number(float(acc.equity))}\n"
                    f"현금 잔고    : ${format_number(float(acc.cash))}\n"
                    f"매수력       : ${format_number(float(acc.buying_power))}")
        except Exception as e:
            return f"계좌 조회 실패: {e}"

    async def cmd_orders(self, d: Dict) -> str:
        try:
            orders = self.br.get_open_orders()
            if not orders: return "미체결 주문이 없습니다."
            return "\n".join([format_order(o) for o in orders])
        except Exception as e:
            return f"주문 조회 실패: {e}"

    async def cmd_info(self, d: Dict) -> str:
        sym = d["symbol"]
        price = self.br.latest_price(sym)
        return f"종목: {sym}\n현재가: ${format_number(price) if price else 'N/A'}"

    async def cmd_auto(self, d: Dict) -> str:
        enabled = d["enabled"]
        self.settings.auto.enabled = enabled
        save_settings(self.settings)
        
        if self.scheduler:
            job = self.scheduler.get_job('auto_trade')
            if enabled and self.settings.auto.strategy:
                job.resume()
            else:
                job.pause()
        
        self._append_log({"event": "auto_changed", "enabled": enabled})
        await self._trigger_state_change()
        return f"자동매매가 {'활성화' if enabled else '비활성화'}되었습니다."

    async def cmd_strategy(self, d: Dict) -> str:
        name = d["name"]
        if not os.path.exists(f"config/strategies/{name}.json"):
            return f"전략 '{name}'을 찾을 수 없습니다."
        self.settings.auto.strategy = name
        save_settings(self.settings)
        await self._trigger_state_change()
        return f"전략이 '{name}'으로 설정되었습니다."

    async def cmd_interval(self, d: Dict) -> str:
        seconds = d["seconds"]
        if seconds < 10: return "실행 간격은 최소 10초 이상이어야 합니다."
        self.settings.auto.interval_seconds = seconds
        save_settings(self.settings)

        if self.scheduler:
            self.scheduler.reschedule_job("auto_trade", trigger="interval", seconds=seconds)
        
        await self._trigger_state_change()
        return f"실행 간격이 {seconds}초로 설정되었습니다."

    async def cmd_trade(self, d: Dict) -> str:
        side = d["cmd"].lower()
        sym = d["symbol"]
        qty, bp_pct, budget_usd = d.get("qty"), d.get("bp_pct"), d.get("budget_usd")
        limit_price = d.get("limit_price")

        try:
            if qty is None:
                price = self.br.latest_price(sym)
                if not price: return f"{sym}의 가격 정보를 가져올 수 없습니다."
                
                if bp_pct: budget_usd = self.br.buying_power() * (bp_pct / 100.0)
                if budget_usd: qty = compute_qty_from_budget(price, budget_usd, self.settings.allow_fractional)
                
                if not qty or qty <= 0: return "주문 수량을 계산할 수 없거나 0 이하입니다."

            order_type = "limit" if limit_price else "market"
            order = self.br.submit_order(sym, qty, side, order_type, limit_price=limit_price)
            
            self._append_log({
                "event": "order_submitted", "symbol": sym, "qty": qty, 
                "side": side, "order_type": order_type, 
                "limit_price": limit_price, "order_id": order.id
            })
            
            return (f"주문 성공: {side.upper()} {sym} {qty}주 @ "
                    f"{f'${limit_price}' if order_type == 'limit' else '시장가'}\n"
                    f"주문 ID: {order.id[:8]}...")
        except Exception as e:
            logger.error(f"주문 처리 오류: {e}", exc_info=True)
            return f"주문 실패: {e}"

    async def cmd_cancel(self, d: Dict) -> str:
        try:
            oid = d["order_id"]
            self.br.cancel_order(oid)
            self._append_log({"event": "order_cancelled", "order_id": oid})
            return f"주문 {oid[:8]}... 취소 요청을 보냈습니다."
        except Exception as e:
            return f"주문 취소 실패: {e}"