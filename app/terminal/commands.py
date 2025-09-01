import json
import math
import logging
import glob
from typing import Dict, Any, Callable, Awaitable
from alpaca_client import AlpacaBroker
from config import save_settings, Settings

LOG = logging.getLogger("terminal")

def compute_qty_from_budget(price: float, budget: float, fractional: bool) -> float:
    if price <= 0: return 0
    if fractional:
        return math.floor((budget/price)*100)/100.0
    return math.floor(budget/price)

def _append_log_event(ev: dict):
    LOG.info(json.dumps(ev, ensure_ascii=False))

def _load_history(max_items: int = 50):
    items = []
    files = sorted(glob.glob("logs/*.jsonl"))
    for path in files[::-1]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        outer = json.loads(line)
                        msg = outer.get("msg")
                        ev = json.loads(msg) if isinstance(msg, str) else msg
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if isinstance(ev, dict) and ev.get("event") in ("order_submitted","order_cancelled","mode_changed","auto_changed"):
                        items.append(ev)
        except Exception:
            continue
        if len(items) >= max_items:
            break
    return items[-max_items:]

class TerminalLogic:
    def __init__(self, broker: AlpacaBroker, settings: Settings, scheduler=None, runner=None, on_state_change: Callable[[], Awaitable[None]] = None):
        self.br = broker
        self.settings = settings
        self.scheduler = scheduler
        self.runner = runner
        self.on_state_change = on_state_change

    async def _trigger_state_change(self):
        if self.on_state_change:
            await self.on_state_change()

    async def handle(self, d: Dict[str, Any]) -> str:
        cmd = d.get("cmd")

        if cmd == "HELP":
            return (
                "사용 가능한 명령어:\n"
                "  HELP                  : 도움말 보기\n"
                "  STATUS                : 현재 상태 조회\n"
                "  PORTFOLIO             : 보유 포지션 조회\n"
                "  ORDERS                : 미체결 주문 조회\n"
                "  HISTORY               : 최근 거래 내역 조회\n"
                "  .{TICKER}              : (예: .AAPL) 현재가 및 보유 정보 조회\n"
                "  BUY/SELL .{TICKER} ... : (예: BUY .AAPL 10) 개별 종목 매매\n"
                "  BUY/SELL {myETF} ...  : (예: BUY myETF1 $1000) myETF 매매\n"
                "  CANCEL {ORDER_ID}     : 주문 취소\n"
                "  MODE {PAPER|LIVE}     : 거래 모드 변경\n"
                "  AUTO {ON|OFF}         : 자동매매 시작/정지"
            )
        if cmd == "STATUS":
            auto = "ON" if self.settings.auto.enabled else "OFF"
            creds = "OK" if self.br.enabled else "인증 실패"
            return f"모드={self.settings.mode} | 자동매매={auto} | 전략={self.settings.auto.strategy} | Alpaca 인증={creds}"

        if cmd == "PORTFOLIO":
            try:
                pos = self.br.positions()
                if not pos: return "보유 포지션이 없습니다."
                lines = [f"{p.symbol:<10} | 수량: {p.qty:<10} | 평단가: ${p.avg_entry_price}" for p in pos]
                return "\n".join(lines)
            except Exception as e:
                return f"포트폴리오 조회 실패: {e}"

        if cmd == "ORDERS":
            try:
                orders = self.br.get_open_orders()
                if not orders: return "미체결 주문이 없습니다."
                lines = [f"{o.id} | {o.symbol:<7} {o.side:<4} | 수량: {o.qty:<8} | 타입: {o.type}" for o in orders]
                return "\n".join(lines)
            except Exception as e:
                return f"미체결 주문 조회 실패: {e}"

        if cmd == "HISTORY":
            rows = _load_history(50)
            if not rows: return "최근 거래 내역이 없습니다."
            out=[]
            for r in rows:
                if r["event"] == "order_submitted":
                    out.append(f"주문: {r['side']} {r['symbol']} 수량={r['qty']} 가격={r.get('limit_price','MKT')}")
                elif r["event"] == "order_cancelled":
                    out.append(f"취소: {r['order_id']}")
                elif r["event"] == "mode_changed":
                    out.append(f"모드 변경 → {r['mode']}")
                elif r["event"] == "auto_changed":
                    out.append(f"자동매매 → {'ON' if r['enabled'] else 'OFF'}")
            return "\n".join(out)

        if cmd == "INFO":
            sym = d["symbol"]
            try:
                price = self.br.latest_price(sym)
                held_qty = 0
                for p in self.br.positions():
                    if p.symbol == sym: held_qty = p.qty
                return f"심볼: {sym} | 현재가: ${price or 'N/A'} | 보유 수량: {held_qty}"
            except Exception as e:
                return f"정보 조회 실패: {e}"

        if cmd == "MODE":
            self.settings.mode = d["mode"]
            save_settings(self.settings)
            self.br.__init__(self.settings)
            _append_log_event({"event":"mode_changed", "mode":self.settings.mode})
            await self._trigger_state_change()
            return f"거래 모드가 {self.settings.mode} (으)로 변경되었습니다."

        if cmd == "AUTO":
            self.settings.auto.enabled = d["enabled"]
            save_settings(self.settings)
            if self.scheduler:
                if d["enabled"]:
                    if not self.scheduler.running: self.scheduler.start()
                    elif self.scheduler.paused: self.scheduler.resume()
                elif self.scheduler.running and not self.scheduler.paused:
                    self.scheduler.pause()
            _append_log_event({"event":"auto_changed", "enabled":self.settings.auto.enabled})
            await self._trigger_state_change()
            return f"자동매매가 {'ON' if d['enabled'] else 'OFF'} 상태로 변경되었습니다."

        if cmd in ("BUY", "SELL"):
            side = "buy" if cmd == "BUY" else "sell"
            target = d["target"]
            try:
                if target == "TICKER":
                    sym, qty, limit = d["symbol"], d.get("qty"), d.get("limit_price")
                    bp_pct, budget_usd = d.get("bp_pct"), d.get("budget_usd")
                    
                    if qty is None:
                        price = self.br.latest_price(sym) or 0
                        if bp_pct: budget_usd = self.br.buying_power() * (bp_pct / 100.0)
                        if budget_usd: qty = compute_qty_from_budget(price, budget_usd, self.settings.allow_fractional)
                        if qty is None or qty <= 0: return "주문 수량을 계산할 수 없습니다. (예산 부족 또는 가격 정보 없음)"
                    
                    order_type = "market" if limit is None else "limit"
                    o = self.br.submit_order(sym, qty, side, order_type, limit_price=limit)
                    _append_log_event({"event":"order_submitted", "symbol":sym, "qty":qty, "side":side, "order_type":order_type, "limit_price":limit, "order_id":o.id})
                    return f"주문 성공: {cmd} {sym} {qty}주 (ID: {o.id})"

                if target == "MYETF":
                    with open("config/myETFs.json", "r", encoding="utf-8") as f: etfs = json.load(f)
                    key = d["key"]
                    if key not in etfs: return f"myETF '{key}'를 찾을 수 없습니다."
                    
                    weight = etfs[key]
                    lines=[]
                    if side == "buy":
                        budget = d.get("budget_usd")
                        if d.get("bp_pct"): budget = self.br.buying_power() * (d["bp_pct"]/100.0)
                        if not budget: return "매수 예산을 지정하세요 (예: $1000 또는 10%)"
                        
                        for sym, pct in weight.items():
                            price = self.br.latest_price(sym) or 0
                            alloc = budget * (pct/100.0)
                            qty = compute_qty_from_budget(price, alloc, self.settings.allow_fractional)
                            if qty <= 0: continue
                            o = self.br.submit_order(sym, qty, "buy", "market")
                            _append_log_event({"event":"order_submitted","symbol":sym,"qty":qty,"side":"buy","order_type":"market","order_id":o.id})
                            lines.append(f"BUY {sym} {qty}주 → {o.id}")
                    else: # SELL
                        held = {p.symbol: float(p.qty) for p in self.br.positions()}
                        bp_pct = d.get("bp_pct")
                        budget = d.get("budget_usd")
                        if not bp_pct and not budget: return "매도할 비율(%) 또는 금액($)을 지정하세요."
                        
                        for sym, pct in weight.items():
                            if sym not in held or held[sym] <= 0: continue
                            qty_to_sell = 0
                            if bp_pct: # 보유 수량의 % 만큼 매도
                                qty_to_sell = round(held[sym] * (bp_pct / 100.0), 2 if self.settings.allow_fractional else 0)
                            elif budget: # 전체 ETF의 가치 중 특정 금액만큼 비중대로 매도
                                price = self.br.latest_price(sym) or 0
                                alloc = budget * (pct/100.0)
                                qty_to_sell = min(held[sym], compute_qty_from_budget(price, alloc, self.settings.allow_fractional))
                            
                            if qty_to_sell <= 0: continue
                            o = self.br.submit_order(sym, qty_to_sell, "sell", "market")
                            _append_log_event({"event":"order_submitted","symbol":sym,"qty":qty_to_sell,"side":"sell","order_type":"market","order_id":o.id})
                            lines.append(f"SELL {sym} {qty_to_sell}주 → {o.id}")

                    return "\n".join(lines) if lines else "실행된 주문이 없습니다."

            except Exception as e:
                LOG.error(f"주문 처리 중 오류 발생: {e}", exc_info=True)
                return f"주문 실패: {e}"

        if cmd == "CANCEL":
            try:
                oid = d["order_id"]
                self.br.cancel_order(oid)
                _append_log_event({"event":"order_cancelled", "order_id":oid})
                return f"주문 {oid} 취소 요청을 보냈습니다."
            except Exception as e:
                return f"주문 취소 실패: {e}"

        return "알 수 없는 명령어입니다. 도움말은 HELP를 입력하세요."