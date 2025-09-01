# app/terminal/commands.py
import json
import math
import logging
import glob
import os
from datetime import datetime
from typing import Dict, Any, Callable, Awaitable, Optional
from alpaca_client import AlpacaBroker
from config import save_settings, Settings

logger = logging.getLogger("terminal")

def compute_qty_from_budget(price: float, budget: float, fractional: bool) -> float:
    """예산으로 수량 계산"""
    if price <= 0:
        return 0
    if fractional:
        return math.floor((budget / price) * 100) / 100.0
    return math.floor(budget / price)

def format_number(value: float, decimals: int = 2) -> str:
    """숫자 포맷팅"""
    return f"{value:,.{decimals}f}"

def format_order(order) -> str:
    """주문 정보 포맷팅"""
    return (
        f"ID: {order.id[:8]}... | "
        f"{order.symbol} {order.side} {order.qty}주 | "
        f"타입: {order.order_type} | "
        f"상태: {order.status}"
    )

def format_position(position) -> str:
    """포지션 정보 포맷팅"""
    current_value = float(position.market_value)
    cost_basis = float(position.cost_basis)
    pnl = current_value - cost_basis
    pnl_pct = (pnl / cost_basis * 100) if cost_basis != 0 else 0
    
    return (
        f"{position.symbol:<8} | "
        f"수량: {position.qty:<10} | "
        f"평단가: ${format_number(float(position.avg_entry_price))} | "
        f"현재가치: ${format_number(current_value)} | "
        f"손익: ${format_number(pnl)} ({pnl_pct:+.2f}%)"
    )
def format_price_change(current: float, previous: float, language: str = "ko") -> str:
    """가격 변화를 언어 설정에 맞게 포맷"""
    if previous == 0:
        return ""
    
    change = current - previous
    change_pct = (change / previous) * 100
    
    if language == "us":
        # 미국식: + 녹색, - 빨강
        if change >= 0:
            color = "\033[92m"  # 녹색
            symbol = "▲"
        else:
            color = "\033[91m"  # 빨강
            symbol = "▼"
    else:
        # 한국식: + 빨강, - 파랑
        if change >= 0:
            color = "\033[91m"  # 빨강
            symbol = "▲"
        else:
            color = "\033[94m"  # 파랑
            symbol = "▼"
    
    reset = "\033[0m"
    return f"{color}{symbol} ${abs(change):.2f} ({change_pct:+.2f}%){reset}"
class TerminalLogic:
    """터미널 명령어 로직"""
    
    def __init__(self, broker: AlpacaBroker, settings: Settings, 
                 scheduler=None, runner=None,
                 on_state_change: Callable[[], Awaitable[None]] = None):
        self.br = broker
        self.settings = settings
        self.scheduler = scheduler
        self.runner = runner
        self.on_state_change = on_state_change
    
    async def _trigger_state_change(self):
        """상태 변경 트리거"""
        if self.on_state_change:
            await self.on_state_change()
    
    def _append_log(self, event: dict):
        """로그 추가"""
        logger.info(json.dumps(event, ensure_ascii=False))
    
    def _load_history(self, max_items: int = 50):
        """거래 내역 로드"""
        items = []
        log_files = sorted(glob.glob("logs/*.jsonl"))
        
        for path in log_files[::-1]:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            msg = data.get("msg")
                            if isinstance(msg, str):
                                try:
                                    event = json.loads(msg)
                                except:
                                    continue
                            else:
                                event = msg
                            
                            if isinstance(event, dict) and event.get("event") in [
                                "order_submitted", "order_cancelled", 
                                "mode_changed", "auto_changed"
                            ]:
                                items.append(event)
                                
                        except json.JSONDecodeError:
                            continue
                            
            except Exception:
                continue
            
            if len(items) >= max_items:
                break
        
        return items[-max_items:]
    
    async def handle(self, d: Dict[str, Any]) -> str:
        """명령어 처리"""
        cmd = d.get("cmd")
        
        # HELP 명령어
        if cmd == "HELP":
            return """
╔══════════════════════════════════════════════════════════════╗
║                    MCMUGANE 터미널 명령어                    ║
╠══════════════════════════════════════════════════════════════╣
║ 기본 명령어:                                                 ║
║   HELP                 - 도움말 보기                         ║
║   STATUS               - 현재 상태 조회                      ║
║   CLEAR                - 화면 지우기                         ║
║                                                              ║
║ 계좌 정보:                                                   ║
║   PORTFOLIO            - 보유 포지션 조회                    ║
║   POSITIONS            - 포지션 상세 조회                    ║
║   BALANCE              - 계좌 잔고 조회                      ║
║   ORDERS               - 미체결 주문 조회                    ║
║   HISTORY              - 최근 거래 내역                      ║
║                                                              ║
║ 종목 조회:                                                   ║
║   .{TICKER}            - 종목 정보 (예: .AAPL)              ║
║                                                              ║
║ 매매 명령:                                                   ║
║   BUY .{TICKER} [수량/금액/%]  - 매수                       ║
║     예: BUY .AAPL 10          (10주)                        ║
║     예: BUY .AAPL $1000       (1000달러만큼)                ║
║     예: BUY .AAPL 5%          (매수력의 5%)                 ║
║                                                              ║
║   SELL .{TICKER} [수량/금액/%] - 매도                       ║
║   BUY/SELL {myETF} [금액/%]   - ETF 매매                    ║
║   CANCEL {ORDER_ID}            - 주문 취소                   ║
║                                                              ║
║ 시스템 설정:                                                 ║
║   MODE {PAPER|LIVE}    - 거래 모드 변경                     ║
║   AUTO {ON|OFF}        - 자동매매 켜기/끄기                 ║
║   STRATEGY {name}      - 전략 설정                          ║
║   INTERVAL {seconds}   - 실행 간격 설정                     ║
╚══════════════════════════════════════════════════════════════╝
"""
        
        # STATUS 명령어
        if cmd == "STATUS":
            from config import get_market_status
            
            auto = "ON" if self.settings.auto.enabled else "OFF"
            creds = "연결됨" if self.br.enabled else "연결 안됨"
            strategy = self.settings.auto.strategy or "없음"
            interval = self.settings.auto.interval_seconds
            market = get_market_status()
            
            status_lines = [
                "=" * 50,
                "시스템 상태",
                "=" * 50,
                f"거래 모드    : {self.settings.mode}",
                f"자동매매     : {auto}",
                f"활성 전략    : {strategy}",
                f"실행 간격    : {interval}초",
                f"Alpaca 연결  : {creds}",
                f"언어 설정    : {self.settings.language.upper()}",
                f"시장 상태    : {market['status']}",
                f"뉴욕 시간    : {market['ny_time']}",
            ]
            
            if not market['is_open'] and market['next_open']:
                status_lines.append(f"다음 개장    : {market['next_open']}")
            
            if self.br.enabled:
                try:
                    bp = self.br.buying_power()
                    status_lines.append(f"매수력       : ${format_number(bp)}")
                except:
                    pass
            
            status_lines.append("=" * 50)
            return "\n".join(status_lines)
        
        # CLEAR 명령어
        if cmd == "CLEAR":
            return "\033[2J\033[H"  # ANSI escape code for clear screen
        
        # PORTFOLIO 명령어
        if cmd == "PORTFOLIO":
            try:
                positions = self.br.positions()
                if not positions:
                    return "보유 포지션이 없습니다."
                
                lines = ["=" * 80, "포트폴리오", "=" * 80]
                total_value = 0
                total_cost = 0
                
                for p in positions:
                    lines.append(format_position(p))
                    total_value += float(p.market_value)
                    total_cost += float(p.cost_basis)
                
                total_pnl = total_value - total_cost
                total_pnl_pct = (total_pnl / total_cost * 100) if total_cost != 0 else 0
                
                lines.append("=" * 80)
                lines.append(f"총 평가액: ${format_number(total_value)} | "
                           f"총 손익: ${format_number(total_pnl)} ({total_pnl_pct:+.2f}%)")
                
                return "\n".join(lines)
                
            except Exception as e:
                return f"포트폴리오 조회 실패: {e}"
        
        # POSITIONS 명령어 (PORTFOLIO와 동일)
        if cmd == "POSITIONS":
            return await self.handle({"cmd": "PORTFOLIO"})
        
        # BALANCE 명령어
        if cmd == "BALANCE":
            try:
                account = self.br.account()
                lines = [
                    "=" * 50,
                    "계좌 정보",
                    "=" * 50,
                    f"계좌 가치    : ${format_number(float(account.equity))}",
                    f"현금 잔고    : ${format_number(float(account.cash))}",
                    f"매수력       : ${format_number(float(account.buying_power))}",
                    f"포지션 가치  : ${format_number(float(account.long_market_value))}",
                    "=" * 50
                ]
                return "\n".join(lines)
                
            except Exception as e:
                return f"계좌 조회 실패: {e}"
        
        # ORDERS 명령어
        if cmd == "ORDERS":
            try:
                orders = self.br.get_open_orders()
                if not orders:
                    return "미체결 주문이 없습니다."
                
                lines = ["=" * 80, "미체결 주문", "=" * 80]
                for o in orders:
                    lines.append(format_order(o))
                lines.append("=" * 80)
                
                return "\n".join(lines)
                
            except Exception as e:
                return f"주문 조회 실패: {e}"
        
        # HISTORY 명령어
        if cmd == "HISTORY":
            rows = self._load_history(30)
            if not rows:
                return "최근 거래 내역이 없습니다."
            
            lines = ["=" * 80, "최근 거래 내역 (최근 30건)", "=" * 80]
            
            for r in rows:
                timestamp = r.get("timestamp", "")
                if r["event"] == "order_submitted":
                    lines.append(
                        f"[주문] {r['side'].upper()} {r['symbol']} "
                        f"{r['qty']}주 @ "
                        f"{'시장가' if r['order_type'] == 'market' else f'${r.get('limit_price', 0)}'}"
                    )
                elif r["event"] == "order_cancelled":
                    lines.append(f"[취소] 주문 ID: {r['order_id'][:8]}...")
                elif r["event"] == "mode_changed":
                    lines.append(f"[설정] 모드 변경 → {r['mode']}")
                elif r["event"] == "auto_changed":
                    lines.append(f"[설정] 자동매매 → {'ON' if r['enabled'] else 'OFF'}")
            
            lines.append("=" * 80)
            return "\n".join(lines)
        
        # INFO 명령어 (종목 정보)
        if cmd == "INFO":
            sym = d["symbol"]
            try:
                price = self.br.latest_price(sym)
                
                # 보유 수량 확인
                held_qty = 0
                held_value = 0
                for p in self.br.positions():
                    if p.symbol == sym:
                        held_qty = float(p.qty)
                        held_value = float(p.market_value)
                
                lines = [
                    f"=" * 40,
                    f"종목: {sym}",
                    f"현재가: ${format_number(price) if price else 'N/A'}",
                    f"보유 수량: {held_qty}주",
                ]
                
                if held_qty > 0:
                    lines.append(f"평가 금액: ${format_number(held_value)}")
                
                lines.append("=" * 40)
                return "\n".join(lines)
                
            except Exception as e:
                return f"정보 조회 실패: {e}"
        
        # MODE 명령어
        if cmd == "MODE":
            new_mode = d["mode"]
            self.settings.mode = new_mode
            save_settings(self.settings)
            
            # Broker 재초기화
            self.br.__init__(self.settings)
            
            self._append_log({"event": "mode_changed", "mode": new_mode})
            await self._trigger_state_change()
            
            return f"거래 모드가 {new_mode}로 변경되었습니다."
        
        # AUTO 명령어
        if cmd == "AUTO":
            enabled = d["enabled"]
            self.settings.auto.enabled = enabled
            save_settings(self.settings)
            
            if self.scheduler:
                if enabled:
                    if not self.scheduler.running:
                        self.scheduler.start()
                else:
                    if self.scheduler.running:
                        self.scheduler.pause()
            
            self._append_log({"event": "auto_changed", "enabled": enabled})
            await self._trigger_state_change()
            
            return f"자동매매가 {'활성화' if enabled else '비활성화'}되었습니다."
        
        # STRATEGY 명령어
        if cmd == "STRATEGY":
            strategy_name = d["name"]
            
            # 전략 파일 확인
            strategy_path = f"config/strategies/{strategy_name}.json"
            if not os.path.exists(strategy_path):
                return f"전략 '{strategy_name}'을 찾을 수 없습니다."
            
            self.settings.auto.strategy = strategy_name
            save_settings(self.settings)
            
            await self._trigger_state_change()
            return f"전략이 '{strategy_name}'으로 설정되었습니다."
        
        # INTERVAL 명령어
        if cmd == "INTERVAL":
            seconds = d["seconds"]
            if seconds < 10:
                return "실행 간격은 최소 10초 이상이어야 합니다."
            
            self.settings.auto.interval_seconds = seconds
            save_settings(self.settings)
            
            # 스케줄러 업데이트
            if self.scheduler and self.scheduler.get_job("auto"):
                self.scheduler.reschedule_job(
                    "auto",
                    trigger="interval",
                    seconds=seconds
                )
            
            await self._trigger_state_change()
            return f"실행 간격이 {seconds}초로 설정되었습니다."
        
        # BUY/SELL 명령어
        if cmd in ("BUY", "SELL"):
            return await self._handle_trade(d)
        
        # CANCEL 명령어
        if cmd == "CANCEL":
            try:
                oid = d["order_id"]
                self.br.cancel_order(oid)
                self._append_log({"event": "order_cancelled", "order_id": oid})
                return f"주문 {oid[:8]}... 취소 요청을 보냈습니다."
                
            except Exception as e:
                return f"주문 취소 실패: {e}"
        
        # 알 수 없는 명령어
        return f"알 수 없는 명령어: '{d.get('raw', cmd)}'\n도움말은 HELP를 입력하세요."
    
    async def _handle_trade(self, d: Dict[str, Any]) -> str:
        """매매 명령 처리"""
        side = "buy" if d["cmd"] == "BUY" else "sell"
        target = d["target"]
        
        try:
            if target == "TICKER":
                # 개별 종목 매매
                sym = d["symbol"]
                qty = d.get("qty")
                bp_pct = d.get("bp_pct")
                budget_usd = d.get("budget_usd")
                limit_price = d.get("limit_price")
                
                # 수량 계산
                if qty is None:
                    price = self.br.latest_price(sym)
                    if not price or price <= 0:
                        return f"{sym}의 가격 정보를 가져올 수 없습니다."
                    
                    if bp_pct:
                        budget_usd = self.br.buying_power() * (bp_pct / 100.0)
                    
                    if budget_usd:
                        qty = compute_qty_from_budget(
                            price, budget_usd, 
                            self.settings.allow_fractional
                        )
                    
                    if qty is None or qty <= 0:
                        return "주문 수량을 계산할 수 없습니다."
                
                # 주문 제출
                order_type = "limit" if limit_price else "market"
                order = self.br.submit_order(
                    sym, qty, side, order_type, 
                    limit_price=limit_price
                )
                
                self._append_log({
                    "event": "order_submitted",
                    "symbol": sym,
                    "qty": qty,
                    "side": side,
                    "order_type": order_type,
                    "limit_price": limit_price,
                    "order_id": order.id
                })
                
                return (
                    f"주문 성공!\n"
                    f"{side.upper()} {sym} {qty}주 "
                    f"@ {'시장가' if order_type == 'market' else f'${limit_price}'}\n"
                    f"주문 ID: {order.id[:8]}..."
                )
            
            elif target == "MYETF":
                # ETF 매매
                with open("config/myETFs.json", "r", encoding="utf-8") as f:
                    etfs = json.load(f)
                
                key = d["key"]
                if key not in etfs:
                    return f"ETF '{key}'를 찾을 수 없습니다."
                
                weights = etfs[key]
                lines = [f"ETF '{key}' 매매 시작"]
                
                if side == "buy":
                    # 매수
                    budget = d.get("budget_usd")
                    if d.get("bp_pct"):
                        budget = self.br.buying_power() * (d["bp_pct"] / 100.0)
                    
                    if not budget:
                        return "매수 예산을 지정하세요."
                    
                    for sym, pct in weights.items():
                        try:
                            price = self.br.latest_price(sym)
                            if not price or price <= 0:
                                lines.append(f"  {sym}: 가격 정보 없음")
                                continue
                            
                            alloc = budget * (pct / 100.0)
                            qty = compute_qty_from_budget(
                                price, alloc, 
                                self.settings.allow_fractional
                            )
                            
                            if qty <= 0:
                                continue
                            
                            order = self.br.submit_order(
                                sym, qty, "buy", "market"
                            )
                            
                            self._append_log({
                                "event": "order_submitted",
                                "symbol": sym,
                                "qty": qty,
                                "side": "buy",
                                "order_type": "market",
                                "order_id": order.id,
                                "etf": key
                            })
                            
                            lines.append(f"  BUY {sym} {qty}주 → 주문 ID: {order.id[:8]}...")
                            
                        except Exception as e:
                            lines.append(f"  {sym}: 주문 실패 - {e}")
                
                else:
                    # 매도
                    held = {p.symbol: float(p.qty) for p in self.br.positions()}
                    bp_pct = d.get("bp_pct")
                    budget = d.get("budget_usd")
                    
                    if not bp_pct and not budget:
                        return "매도할 비율(%) 또는 금액($)을 지정하세요."
                    
                    for sym, pct in weights.items():
                        if sym not in held or held[sym] <= 0:
                            continue
                        
                        try:
                            qty_to_sell = 0
                            
                            if bp_pct:
                                qty_to_sell = round(
                                    held[sym] * (bp_pct / 100.0),
                                    2 if self.settings.allow_fractional else 0
                                )
                            elif budget:
                                price = self.br.latest_price(sym)
                                if price and price > 0:
                                    alloc = budget * (pct / 100.0)
                                    qty_to_sell = min(
                                        held[sym],
                                        compute_qty_from_budget(
                                            price, alloc,
                                            self.settings.allow_fractional
                                        )
                                    )
                            
                            if qty_to_sell <= 0:
                                continue
                            
                            order = self.br.submit_order(
                                sym, qty_to_sell, "sell", "market"
                            )
                            
                            self._append_log({
                                "event": "order_submitted",
                                "symbol": sym,
                                "qty": qty_to_sell,
                                "side": "sell",
                                "order_type": "market",
                                "order_id": order.id,
                                "etf": key
                            })
                            
                            lines.append(f"  SELL {sym} {qty_to_sell}주 → 주문 ID: {order.id[:8]}...")
                            
                        except Exception as e:
                            lines.append(f"  {sym}: 주문 실패 - {e}")
                
                return "\n".join(lines) if len(lines) > 1 else "실행된 주문이 없습니다."
                
        except Exception as e:
            logger.error(f"주문 처리 오류: {e}", exc_info=True)
            return f"주문 실패: {e}"