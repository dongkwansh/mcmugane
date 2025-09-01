import re
from typing import Callable, Awaitable
from terminal.parser import parse
from terminal.commands import TerminalLogic

# --- 정규 표현식 상수 ---
TICK = re.compile(r"^\.(?P<ticker>[A-Za-z\.]{1,10})$")
NUM  = re.compile(r"^(?P<num>\d+(\.\d+)?)$")
PCT  = re.compile(r"^(?P<pct>\d+(\.\d+)?)%$")
USD  = re.compile(r"^\$(?P<usd>\d+(\.\d+)?)$")

class TerminalSessionManager:
    # 생성자에 on_state_change 콜백 함수 추가
    def __init__(self, broker, runner, settings, scheduler=None, on_state_change: Callable[[], Awaitable[None]] = None):
        self.logic = TerminalLogic(broker, settings, scheduler=scheduler, on_state_change=on_state_change)
        self.wizard = None # 대화형 입력을 위한 상태 저장 변수

    # AlpacaBroker 객체가 외부에서 변경되었을 때(예: 모드 전환) 호출되는 함수
    def update_broker(self, new_broker):
        self.logic.br = new_broker

    def _reset_wizard(self):
        self.wizard = None

    # 터미널로부터 한 줄의 입력을 받아 처리하는 비동기 함수
    async def handle_line(self, line: str) -> str:
        s = line.strip()
        
        # 대화형 마법사(wizard) 모드 처리
        if self.wizard:
            if s.upper() == "CANCEL":
                self._reset_wizard()
                return "대화형 입력을 취소했습니다."
            
            stage = self.wizard.get("stage")
            
            if stage == "ask_ticker":
                m = TICK.fullmatch(s)
                if not m: return "티커는 .AAPL 형식으로 입력하세요. (취소: CANCEL)"
                self.wizard["symbol"] = m.group("ticker").upper()
                self.wizard["stage"] = "ask_qty"
                return "수량(예: 10), 비율(예: 20%), 또는 금액(예: $200)을 입력하세요."
            
            elif stage == "ask_qty":
                m_num = NUM.fullmatch(s)
                m_pct = PCT.fullmatch(s)
                m_usd = USD.fullmatch(s)
                if m_num: self.wizard["qty"] = float(m_num.group("num"))
                elif m_pct: self.wizard["bp_pct"] = float(m_pct.group("pct"))
                elif m_usd: self.wizard["budget_usd"] = float(m_usd.group("usd"))
                else: return "잘못된 형식입니다. 예: 10 | 20% | $200"
                self.wizard["stage"] = "ask_price"
                return "지정가(예: 150.5)를 입력하거나, 시장가를 원하면 엔터를 누르세요."
            
            elif stage == "ask_price":
                if s:
                    try: self.wizard["limit_price"] = float(s)
                    except ValueError: return "가격은 숫자여야 합니다."
                
                # 마법사에서 수집된 정보로 명령어 딕셔너리 생성
                d = { "cmd": self.wizard["action"], "target": "TICKER", **self.wizard }
                self._reset_wizard()
                return await self.logic.handle(d) # 명령어 로직 실행

        # 일반 명령어 처리
        d = parse(s)
        if d.get("cmd") in ("BUY", "SELL") and d.get("target") == "INTERACTIVE":
            self.wizard = {"action": d["cmd"], "stage": "ask_ticker"}
            return "매수/매도할 티커를 입력하세요. (예: .AAPL)"
        
        return await self.logic.handle(d)