# -*- coding: utf-8 -*-
# 한글 주석: FastAPI 기반 웹 서버 (대시보드 + 터미널)
import os, asyncio, json, datetime, traceback
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import APP_PORT, ACCOUNTS, DEFAULT_ACCOUNT, AUTO_METHODS_DIR, MYETF_DIR, LOGS_DIR
from .trading.alpaca_client import AlpacaClient
from .trading.order_utils import parse_size_token, compute_from_percent, compute_from_notional
from .trading.strategies import list_strategy_files
from .trading.autobot import AutoBot

# 간단 로깅
LOG_PATH = os.path.join(LOGS_DIR, 'app.log')

def log(msg: str):
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")

app = FastAPI(title="Wealth Commander", version="0.1.0")

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), 'static')), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), 'templates'))

# 앱 상태(단일 프로세스 기준)
class AppState:
    def __init__(self):
        self.account: str = DEFAULT_ACCOUNT
        self.extended_hours: bool = False
        self.auto_status_lines: List[str] = []
        self.system_lines: List[str] = []
        self.autobot: Optional[AutoBot] = None
        self.client: Optional[AlpacaClient] = None

STATE = AppState()

def get_client() -> AlpacaClient:
    if STATE.client is None:
        acc = ACCOUNTS.get(STATE.account, ACCOUNTS['paper1'])
        STATE.client = AlpacaClient(acc['key'], acc['secret'], paper=acc['paper'])
    return STATE.client

def switch_account(acc_name: str):
    STATE.account = acc_name
    STATE.client = None  # 재생성하도록
    push_system(f"계좌 전환: {acc_name}")

def push_auto_status(line: str):
    # 최근 5줄만 유지
    STATE.auto_status_lines.append(line)
    del STATE.auto_status_lines[:-5]

def push_system(line: str):
    STATE.system_lines.append(line)
    del STATE.system_lines[:-20]
    log(f"SYS: {line}")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/accounts")
def api_accounts():
    return {"accounts": list(ACCOUNTS.keys()), "selected": STATE.account}

@app.post("/api/select-account")
async def api_select_account(request: Request):
    data = await request.json()
    acc = data.get('account')
    if acc not in ACCOUNTS:
        return JSONResponse({"error": "존재하지 않는 계정"}, status_code=400)
    switch_account(acc)
    return {"ok": True}

@app.post("/api/extended-hours")
async def api_extended_hours(request: Request):
    data = await request.json()
    STATE.extended_hours = bool(data.get('enabled', False))
    push_system(f"Extended Hours {'ON' if STATE.extended_hours else 'OFF'}")
    return {"ok": True, "enabled": STATE.extended_hours}

@app.get("/api/account-info")
def api_account_info():
    client = get_client()
    try:
        acc = client.get_account()
        clock = client.get_clock()
        info = {
            "account_number": acc.get('account_number'),
            "status": acc.get('status'),
            "buying_power": acc.get('buying_power'),
            "portfolio_value": acc.get('portfolio_value'),
            "equity": acc.get('equity'),
            "multiplier": acc.get('multiplier'),
            "daytrade_count": acc.get('daytrade_count'),
            "pattern_day_trader": acc.get('pattern_day_trader'),
            "clock": clock,
        }
        return info
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/strategies")
def api_strategies():
    prefix = f"{STATE.account}_" if STATE.account != 'live' else "live_"
    files = list_strategy_files(AUTO_METHODS_DIR, prefix)
    return {"files": files, "running": STATE.autobot.is_running() if STATE.autobot else False,
            "current": STATE.autobot.current_strategy_name() if STATE.autobot else "(없음)"}

@app.post("/api/strategies/reload")
async def api_strategies_reload():
    # 실제로는 파일 목록만 다시 읽으면 됨
    push_system("전략/myETF JSON 재로딩 완료")
    return {"ok": True}

@app.get("/api/myetf")
def api_myetf():
    out = []
    for name in sorted(os.listdir(MYETF_DIR)):
        if not name.endswith('.json'):
            continue
        p = os.path.join(MYETF_DIR, name)
        try:
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assets = data.get('assets', [])
            s = sum(float(a.get('weight', 0)) for a in assets)
            valid = abs(s - 100.0) < 1e-6
            out.append({"file": name, "sum": s, "valid": valid, "name": data.get('name', name[:-5])})
        except Exception as e:
            out.append({"file": name, "error": str(e), "valid": False})
    return {"myetf": out}

@app.post("/api/autopilot/start")
async def api_autopilot_start(request: Request):
    data = await request.json()
    fname = data.get('file')
    if not fname:
        return JSONResponse({"error": "전략 파일명이 필요합니다."}, status_code=400)
    if STATE.autobot and STATE.autobot.is_running():
        return JSONResponse({"error": "이미 자동매매 실행 중입니다."}, status_code=400)
    client = get_client()
    STATE.autobot = AutoBot(client, send_status_cb=push_auto_status)
    await STATE.autobot.start(fname)
    return {"ok": True}

@app.post("/api/autopilot/stop")
async def api_autopilot_stop():
    if STATE.autobot and STATE.autobot.is_running():
        await STATE.autobot.stop()
    return {"ok": True}

@app.get("/api/autopilot/status")
def api_autopilot_status():
    return {"lines": STATE.auto_status_lines, "running": STATE.autobot.is_running() if STATE.autobot else False}

# ------------------------ 터미널(WebSocket) ------------------------
class TerminalSession:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.history: List[str] = []
        self.pending: Optional[Dict[str, Any]] = None  # 대화형 상태 보관
        self.last_symbol: Optional[str] = None

    async def send(self, s: str):
        await self.ws.send_text(s)

    async def handle(self, raw: str):
        raw = raw.strip()
        if not raw:
            return
        self.history.append(raw)
        self.history = self.history[-10:]  # 최근 10개

        # 대화형 단계가 진행 중이면 우선 처리
        if self.pending:
            await self._handle_pending(raw)
            return

        parts = raw.split()
        cmd = parts[0].lower()
        args = parts[1:]

        try:
            if cmd in ('help', '?'):
                await self._cmd_help()
            elif cmd == 'orders':
                await self._cmd_orders()
            elif cmd == 'history':
                await self._cmd_history()
            elif cmd == 'cancel':
                await self._cmd_cancel(args)
            elif cmd == 'buy':
                await self._cmd_buy(args)
            elif cmd == 'sell':
                await self._cmd_sell(args)
            elif cmd.startswith('.'):  # .TICKER
                await self._cmd_ticker(cmd[1:])
            else:
                await self.send("알 수 없는 명령입니다. 'help'를 입력해 도움말을 보세요.")
        except Exception as e:
            await self.send(f"오류: {e}")
            traceback.print_exc()

    async def _cmd_help(self):
        await self.send(textwrap.dedent("""
        사용 가능한 명령:
          .TICKER                     해당 종목 정보 조회 (예: .SOXL)
          buy [대화형/인자]           예: buy .SOXL 20 | buy .SOXL 20% | buy .SOXL $20 | buy myTECH_01 $1000
          sell [대화형/인자]          예: sell .SOXL 10 | sell .SOXL %50 | sell myTECH_01 $500
          orders                      미체결 주문 목록
          history                     체결 이력 (최근)
          cancel [주문ID|all]         주문 취소
          help                        도움말
        """))

    async def _cmd_orders(self):
        client = get_client()
        orders = client.list_orders(status='open', limit=50)
        if not orders:
            await self.send("열린 주문이 없습니다.")
            return
        await self.send("[Open Orders]")
        for o in orders:
            await self.send(f"- {o.get('id')} {o.get('symbol')} {o.get('side')} {o.get('qty')} @ {o.get('limit_price') or o.get('avg_price')} ({o.get('status')})")


    async def _cmd_history(self):
        client = get_client()
        acts = client.get_activities(activity_types='FILL', page_size=50)
        if not acts:
            await self.send("최근 체결 이력이 없습니다.")
            return
        await self.send("[Recent Fills]")
        for a in acts[:20]:
            await self.send(f"- {a.get('transaction_time')} {a.get('symbol')} {a.get('side')} {a.get('qty')} @ {a.get('price')} ({a.get('order_id')})")


    async def _cmd_cancel(self, args: List[str]):
        client = get_client()
        if not args:
            await self.send("취소할 주문ID 또는 'all'을 입력하세요.")
            return
        target = args[0].lower()
        if target == 'all':
            orders = client.list_orders(status='open')
            n = 0
            for o in orders:
                if client.cancel_order(o.get('id', '')):
                    n += 1
            await self.send(f"{n}개 주문 취소 요청 완료.")
        else:
            ok = client.cancel_order(target)
            await self.send("취소 요청 완료." if ok else "취소 실패 또는 이미 취소됨.")

    async def _cmd_ticker(self, sym: str):
        client = get_client()
        sym = sym.upper()
        self.last_symbol = sym
        last = client.get_latest_trade(sym) or 0.0
        dailies = client.get_daily_ohlc(sym, limit=2) or []
        o = h = l = c = None
        if dailies:
            last_day = dailies[-1]
            o, h, l, c = last_day.get('o'), last_day.get('h'), last_day.get('l'), last_day.get('c')
        positions = client.list_positions()
        pos = next((p for p in positions if p.get('symbol') == sym), None)
        held = "보유중" if pos else "미보유"
        amt = f"{pos.get('qty')}주 / 평단 {pos.get('avg_entry_price')}" if pos else "-"
        await self.send(f"{sym} - 현재가: ${last:.4f} / O:{o} H:{h} L:{l} C:{c} / 보유: {held} {amt}")

    async def _cmd_buy(self, args: List[str]):
        if not args:
            # 대화형 시작
            await self.send(">>> buy")
            await self.send("구매하실 종목(.TICKER 또는 myETF_이름)을 입력하세요:")
            self.pending = {"flow": "buy", "step": "symbol"}
            return

        # 인자 해석
        await self._process_buy_sell_args(flow='buy', args=args)

    async def _cmd_sell(self, args: List[str]):
        if not args:
            await self.send(">>> sell")
            await self.send("매도하실 종목(.TICKER 또는 myETF_이름)을 입력하세요:")
            self.pending = {"flow": "sell", "step": "symbol"}
            return

        await self._process_buy_sell_args(flow='sell', args=args)

    async def _process_buy_sell_args(self, flow: str, args: List[str]):
        # 케이스:
        # 1) buy .SOXL 20
        # 2) buy .SOXL 20%
        # 3) buy .SOXL $20
        # 4) buy .SOXL $20 10
        # 5) buy myETF_XXX $1000
        client = get_client()
        sym_or_etf = args[0]
        limit_price: Optional[float] = None
        size_token: Optional[str] = None
        if len(args) >= 2:
            if args[1][0] in ('$','0','1','2','3','4','5','6','7','8','9'):
                size_token = args[1]
        if len(args) >= 3:
            try:
                limit_price = float(args[2].replace('$',''))
            except:
                limit_price = None

        if sym_or_etf.startswith('.') or sym_or_etf.upper().startswith('MY'):
            # 바로 처리 가능
            await self._execute_order(flow, sym_or_etf, size_token, limit_price)
        else:
            await self.send("종목은 반드시 .TICKER 또는 myETF 이름으로 입력하세요.")

    async def _handle_pending(self, user_input: str):
        flow = self.pending.get('flow')
        step = self.pending.get('step')
        if flow in ('buy','sell'):
            await self._handle_pending_buy_sell(flow, step, user_input)

    async def _handle_pending_buy_sell(self, flow: str, step: str, user_input: str):
        client = get_client()
        if step == 'symbol':
            self.pending['target'] = user_input.strip()
            if not (self.pending['target'].startswith('.') or self.pending['target'].upper().startswith('MY')):
                await self.send("종목은 반드시 .TICKER 또는 myETF 이름으로 입력하세요. 예: .SOXL 또는 myTECH_01")
                return
            # 현재 보유 상황 출력
            await self._print_holding_state(self.pending['target'])
            await self.send("수량, 금액($), 또는 비율(%)로 입력하세요 (예: 20 | $20 | 20%):")
            self.pending['step'] = 'size'
            return
        if step == 'size':
            self.pending['size_token'] = user_input.strip()
            await self.send("목표 가격(예: 30 또는 $30, 생략시 현재가):")
            self.pending['step'] = 'price'
            return
        if step == 'price':
            p = user_input.strip().replace('$','')
            if p:
                try:
                    self.pending['limit_price'] = float(p)
                except:
                    self.pending['limit_price'] = None
            else:
                self.pending['limit_price'] = None
            # 확인 단계
            await self._confirm_pending_order(flow)
            self.pending['step'] = 'confirm'
            return
        if step == 'confirm':
            yn = user_input.strip().lower()
            if yn == 'y':
                await self._execute_order(flow,
                                          self.pending.get('target'),
                                          self.pending.get('size_token'),
                                          self.pending.get('limit_price'))
            else:
                await self.send("주문이 제출되지 않았습니다.")
            self.pending = None
            return

    async def _print_holding_state(self, sym_or_etf: str):
        client = get_client()
        if sym_or_etf.startswith('.'):
            sym = sym_or_etf[1:].upper()
            positions = client.list_positions()
            pos = next((p for p in positions if p.get('symbol') == sym), None)
            amt_line = f"현재 {pos.get('qty')}주 ${float(pos.get('market_value', '0')):.2f} 보유." if pos else "현재 0주 $0 보유."
            await self.send(f"#{amt_line}")
        else:
            await self.send("# myETF 주문은 각 구성 비중대로 분할 매수/매도합니다.")

    async def _confirm_pending_order(self, flow: str):
        target = self.pending.get('target')
        size_token = self.pending.get('size_token')
        limit_price = self.pending.get('limit_price')
        client = get_client()

        if target.startswith('.'):
            sym = target[1:].upper()
            last = client.get_latest_trade(sym) or 0.0
            price = limit_price if limit_price is not None else last
            # 계좌/Buying power
            acc = client.get_account()
            bp = float(acc.get('buying_power', '0'))
            side = '매수' if flow=='buy' else '매도'
            mode, val = parse_size_token(size_token)
            if mode == 'percent':
                qty = compute_from_percent(bp, val, price)
            elif mode == 'notional':
                qty = compute_from_notional(val, price)
            else:
                qty = float(val)
            total = qty * price
            await self.send(f"{sym} {qty}주를 ${price} 에 ${total:.2f} {side}합니다 (y/N): ")
        else:
            # myETF
            etf_file = os.path.join(MYETF_DIR, f"{target}.json" if not target.endswith('.json') else target)
            if not os.path.exists(etf_file):
                await self.send("존재하지 않는 myETF 입니다.")
                return
            acc = client.get_account()
            bp = float(acc.get('buying_power', '0'))
            last = None
            price = limit_price  # myETF는 limit_price 미사용 (개별 심볼 별 현재가로 계산)
            mode, val = parse_size_token(self.pending['size_token'])
            if mode == 'percent':
                notional = bp * (val / 100.0)
            elif mode == 'notional':
                notional = val
            else:
                await self.send("myETF는 금액($) 또는 비율(%)만 입력 가능합니다.")
                notional = 0.0
            await self.send(f"{target} 를 총 ${notional:.2f} 규모로 비중대로 {('매수' if flow=='buy' else '매도')}합니다 (y/N): ")

    async def _execute_order(self, flow: str, sym_or_etf: str, size_token: Optional[str], limit_price: Optional[float]):
        client = get_client()
        side = 'buy' if flow=='buy' else 'sell'

        if sym_or_etf.startswith('.'):
            sym = sym_or_etf[1:].upper()
            last = client.get_latest_trade(sym) or 0.0
            price = limit_price if limit_price is not None else last
            acc = client.get_account()
            bp = float(acc.get('buying_power', '0'))
            if size_token is None:
                await self.send("수량/금액/비율이 없습니다.")
                return
            mode, val = parse_size_token(size_token)
            if mode == 'percent':
                qty = compute_from_percent(bp, val, price)
            elif mode == 'notional':
                qty = compute_from_notional(val, price)
            else:
                qty = float(val)

            resp = client.submit_order(symbol=sym, side=side, qty=qty, type_='limit',
                                       time_in_force='day', limit_price=price,
                                       extended_hours=STATE.extended_hours)
            if 'error' in resp:
                await self.send(f"오류: {resp['error']}")
            else:
                await self.send("주문이 제출되었습니다. Orders 로 확인. Cancel 로 취소.")
            return

        # myETF
        etf_name = sym_or_etf if sym_or_etf.endswith('.json') else f"{sym_or_etf}.json"
        etf_path = os.path.join(MYETF_DIR, etf_name)
        if not os.path.exists(etf_path):
            await self.send("존재하지 않는 myETF 입니다.")
            return
        with open(etf_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assets = data.get('assets', [])
        s = sum(float(a.get('weight', 0)) for a in assets)
        if abs(s - 100.0) > 1e-6:
            await self.send("myETF 비중 합이 100이 아니므로 거래가 비활성화됩니다.")
            return

        acc = client.get_account()
        bp = float(acc.get('buying_power', '0'))
        if size_token is None:
            await self.send("금액($) 또는 비율(%)을 입력하세요.")
            return
        mode, val = parse_size_token(size_token)
        if mode == 'percent':
            total_notional = bp * (val / 100.0)
        elif mode == 'notional':
            total_notional = val
        else:
            await self.send("myETF는 금액($) 또는 비율(%)만 허용됩니다.")
            return

        # 비중 배분하여 각 심볼 주문
        results = []
        for a in assets:
            sym = a['symbol'].lstrip('.').upper()
            w = float(a['weight']) / 100.0
            alloc = total_notional * w
            last = client.get_latest_trade(sym) or 0.0
            qty = compute_from_notional(alloc, last if last>0 else 1.0)
            if qty <= 0:
                continue
            resp = client.submit_order(symbol=sym, side=side, qty=qty, type_='limit',
                                       time_in_force='day', limit_price=(limit_price or last),
                                       extended_hours=STATE.extended_hours)
            oid = resp.get('id') if 'error' not in resp else f"ERR:{resp['error']}"
            results.append(f"{sym} {qty}주 => {oid}")
        await self.send("주문 제출 결과: " + "; ".join(results))

sessions: Dict[str, TerminalSession] = {}

@app.websocket("/ws/terminal")
async def ws_terminal(ws: WebSocket):
    await ws.accept()
    sid = str(id(ws))
    sess = TerminalSession(ws)
    sessions[sid] = sess
    await sess.send("Wealth Commander 터미널에 오신 것을 환영합니다. 'help'를 입력해보세요.")
    try:
        while True:
            msg = await ws.receive_text()
            await sess.handle(msg)
    except WebSocketDisconnect:
        sessions.pop(sid, None)

# ------------------------ 템플릿 라우트 ------------------------
