# app/terminal/session.py
import re
from typing import Callable, Awaitable
from app.terminal.parser import parse # 수정됨
from app.terminal.commands import TerminalLogic # 수정됨

# 정규식 패턴
TICK = re.compile(r"^\.(?P<ticker>[A-Za-z\.]{1,10})$")
NUM = re.compile(r"^(?P<num>\d+(\.\d+)?)$")
PCT = re.compile(r"^(?P<pct>\d+(\.\d+)?)%$")
USD = re.compile(r"^\$(?P<usd>\d+(\.\d+)?)$")

class TerminalSessionManager:
    """터미널 세션 관리"""

    def __init__(self, broker, runner, settings, scheduler=None,
                 on_state_change: Callable[[], Awaitable[None]] = None):
        self.logic = TerminalLogic(
            broker, settings, scheduler=scheduler,
            runner=runner, on_state_change=on_state_change
        )
        self.wizard = None
        self.command_history = []

    def update_broker(self, new_broker):
        """브로커 업데이트"""
        self.logic.br = new_broker

    def _reset_wizard(self):
        """대화형 모드 초기화"""
        self.wizard = None

    async def handle_line(self, line: str) -> str:
        """명령줄 처리"""
        s = line.strip()
        if not s: return ""

        if not self.command_history or self.command_history[-1] != s:
            self.command_history.append(s)
            if len(self.command_history) > 100: self.command_history.pop(0)

        if self.wizard:
            return await self._handle_wizard(s)

        parsed = parse(s)
        if parsed.get("cmd") in ("BUY", "SELL") and parsed.get("target") == "INTERACTIVE":
            self.wizard = {"action": parsed["cmd"], "stage": "ask_ticker"}
            return "티커를 입력하세요 (예: .AAPL) [취소: CANCEL]:"

        return await self.logic.handle(parsed)

    async def _handle_wizard(self, s: str) -> str:
        """대화형 모드 처리"""
        if s.upper() == "CANCEL":
            self._reset_wizard()
            return "취소되었습니다."

        stage = self.wizard.get("stage")

        if stage == "ask_ticker":
            m = TICK.fullmatch(s)
            if not m: return "잘못된 형식입니다. 티커는 .AAPL 형식으로 입력하세요:"
            self.wizard["symbol"] = m.group("ticker").upper()
            self.wizard["stage"] = "ask_qty"
            return "수량을 입력하세요 (예: 10, 20%, $1000):"

        elif stage == "ask_qty":
            m_num, m_pct, m_usd = NUM.fullmatch(s), PCT.fullmatch(s), USD.fullmatch(s)
            if m_num: self.wizard["qty"] = float(m_num.group("num"))
            elif m_pct: self.wizard["bp_pct"] = float(m_pct.group("pct"))
            elif m_usd: self.wizard["budget_usd"] = float(m_usd.group("usd"))
            else: return "잘못된 형식입니다. 예: 10 | 20% | $1000"
            self.wizard["stage"] = "ask_price"
            return "지정가를 입력하거나 Enter(시장가):"

        elif stage == "ask_price":
            if s:
                try: self.wizard["limit_price"] = float(s)
                except ValueError: return "가격은 숫자여야 합니다:"

            command_to_run = {"cmd": self.wizard["action"], "target": "TICKER", **self.wizard}
            self._reset_wizard()
            return await self.logic.handle(command_to_run)

        return "알 수 없는 상태입니다."