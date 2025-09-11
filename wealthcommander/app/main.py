# -*- coding: utf-8 -*-
# 한글 주석: FastAPI 기반 웹 서버 (대시보드 + 터미널)
import os, asyncio, json, datetime, traceback, textwrap
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import APP_PORT, ACCOUNTS, DEFAULT_ACCOUNT, AUTO_METHODS_DIR, MYETF_DIR, LOGS_DIR
from .trading.alpaca_client import AlpacaClient
from .trading.order_utils import parse_size_token, compute_from_percent, compute_from_notional
from .trading.strategies import list_strategy_files, load_strategy_file
from .trading.autobot import AutoBot

# 간단 로깅
LOG_PATH = os.path.join(LOGS_DIR, 'app.log')

def log(msg: str):
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
    except Exception as e:
        print(f"로깅 실패: {e}")

app = FastAPI(title="Wealth Commander", version="0.2.1")

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
        self.websockets: List[WebSocket] = []
        self.current_strategy_info: Optional[Dict[str, Any]] = None

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
    # 최근 10줄로 증가
    STATE.auto_status_lines.append(line)
    if len(STATE.auto_status_lines) > 10:
        STATE.auto_status_lines = STATE.auto_status_lines[-10:]

def push_system(line: str):
    STATE.system_lines.append(line)
    if len(STATE.system_lines) > 20:
        STATE.system_lines = STATE.system_lines[-20:]
    log(f"SYS: {line}")
    
    # 시스템 메시지는 로그에만 기록, 터미널에는 전송하지 않음

def list_myetf_files() -> List[str]:
    """myETF 파일 목록 반환"""
    if not os.path.exists(MYETF_DIR):
        os.makedirs(MYETF_DIR, exist_ok=True)
        return []
    
    files = []
    for fname in sorted(os.listdir(MYETF_DIR)):
        if fname.endswith('.json'):
            files.append(fname)  # .json 포함하여 반환
    return files

def validate_myetf(name: str) -> tuple[bool, Optional[Dict[str, Any]], str]:
    """myETF 유효성 검사
    Returns: (valid, data, error_msg)
    """
    # 확장자가 없으면 추가
    if not name.endswith('.json'):
        name = name + '.json'
    
    filepath = os.path.join(MYETF_DIR, name)
    
    if not os.path.exists(filepath):
        return False, None, f"파일이 존재하지 않음: {name}"
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assets = data.get('assets', [])
        if not assets:
            return False, None, "자산 구성이 비어있음"
        
        total_weight = sum(float(a.get('weight', 0)) for a in assets)
        if abs(total_weight - 100.0) > 0.01:
            return False, data, f"비중 합계가 100이 아님: {total_weight:.2f}%"
        
        return True, data, ""
    
    except Exception as e:
        return False, None, f"파일 읽기 오류: {str(e)}"

@app.get("/health")
def health():
    return {"status": "ok", "version": "0.2.1"}

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
    
    # 자동매매 실행 중이면 중지
    if STATE.autobot and STATE.autobot.is_running():
        await STATE.autobot.stop()
        push_system(f"계좌 전환으로 자동매매 중지됨")
    
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
        
        # 숫자 포맷팅 개선 - 문자열로 반환
        info = {
            "account_number": acc.get('account_number'),
            "status": acc.get('status'),
            "buying_power": float(acc.get('buying_power', 0)),
            "portfolio_value": float(acc.get('portfolio_value', 0)),
            "equity": float(acc.get('equity', 0)),
            "multiplier": acc.get('multiplier'),
            "daytrade_count": acc.get('daytrade_count'),
            "pattern_day_trader": acc.get('pattern_day_trader'),
            "clock": clock,
        }
        return info
    except Exception as e:
        log(f"계좌 정보 조회 실패: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/strategies")
def api_strategies():
    prefix = f"{STATE.account}_" if STATE.account != 'live' else "live_"
    files = list_strategy_files(AUTO_METHODS_DIR, prefix)
    
    # 현재 선택된 전략 정보 로드
    strategy_info = None
    if STATE.current_strategy_info:
        strategy_info = STATE.current_strategy_info
    
    return {
        "files": files, 
        "running": STATE.autobot.is_running() if STATE.autobot else False,
        "current": STATE.autobot.current_strategy_name() if STATE.autobot else "(없음)",
        "strategy_info": strategy_info
    }

@app.get("/api/strategy-detail/{filename}")
def api_strategy_detail(filename: str):
    """전략 파일 상세 정보 반환"""
    try:
        filepath = os.path.join(AUTO_METHODS_DIR, filename)
        if not os.path.exists(filepath):
            return JSONResponse({"error": "파일이 존재하지 않음"}, status_code=404)
        
        strategy = load_strategy_file(filepath)
        
        # 요약 정보 생성
        summary = {
            "name": strategy.get('name', filename),
            "strategy_type": strategy.get('strategy_type', 'unknown'),
            "universe": strategy.get('universe', []),
            "timeframe": strategy.get('timeframe', '15Min'),
            "params": strategy.get('params', {}),
            "risk": strategy.get('risk', {}),
            "order": strategy.get('order', {}),
            "rebalance": strategy.get('rebalance', {}),
            "extended_hours": strategy.get('extended_hours', False),
            "enabled": strategy.get('enabled', True)
        }
        
        return summary
    except Exception as e:
        log(f"전략 상세 조회 실패: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/strategies/reload")
async def api_strategies_reload():
    push_system("전략/myETF JSON 재로딩 완료")
    return {"ok": True}

@app.get("/api/myetf")
def api_myetf():
    out = []
    if not os.path.exists(MYETF_DIR):
        os.makedirs(MYETF_DIR, exist_ok=True)
        return {"myetf": out}
    
    for name in sorted(os.listdir(MYETF_DIR)):
        if not name.endswith('.json'):
            continue
        p = os.path.join(MYETF_DIR, name)
        try:
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assets = data.get('assets', [])
            s = sum(float(a.get('weight', 0)) for a in assets)
            valid = abs(s - 100.0) < 0.01  # 소수점 오차 허용
            out.append({
                "file": name, 
                "sum": round(s, 2), 
                "valid": valid, 
                "name": data.get('name', name[:-5]),
                "assets": assets
            })
        except Exception as e:
            out.append({"file": name, "error": str(e), "valid": False})
    return {"myetf": out}

@app.post("/api/autopilot/start")
async def api_autopilot_start(request: Request):
    data = await request.json()
    fname = data.get('file')
    if not fname:
        return JSONResponse({"error": "전략 파일명이 필요합니다."}, status_code=400)
    
    # 전략 파일 존재 확인
    strategy_path = os.path.join(AUTO_METHODS_DIR, fname)
    if not os.path.exists(strategy_path):
        return JSONResponse({"error": f"전략 파일이 존재하지 않음: {fname}"}, status_code=404)
    
    if STATE.autobot and STATE.autobot.is_running():
        return JSONResponse({"error": "이미 자동매매 실행 중입니다."}, status_code=400)
    
    try:
        # 전략 정보 로드
        strategy = load_strategy_file(strategy_path)
        STATE.current_strategy_info = strategy
        
        # 시작 정보 로깅 - 미국식 날짜 표시
        now = datetime.datetime.now()
        push_auto_status(f"===== 자동매매 시작 =====")
        push_auto_status(f"[{now:%m/%d %I:%M %p}]")
        push_auto_status(f"전략: {strategy.get('name', fname)}")
        push_auto_status(f"타입: {strategy.get('strategy_type', 'unknown')}")
        push_auto_status(f"종목: {', '.join([s.lstrip('.') for s in strategy.get('universe', [])])}")
        push_auto_status(f"타임프레임: {strategy.get('timeframe', '15Min')}")
        push_auto_status(f"최대 포지션: {strategy.get('risk', {}).get('max_positions', 5)}")
        push_auto_status(f"종목당 최대: ${strategy.get('risk', {}).get('max_notional_per_symbol', 1000):,}")
        
        client = get_client()
        STATE.autobot = AutoBot(client, send_status_cb=push_auto_status)
        
        await STATE.autobot.start(fname)
        push_system(f"자동매매 시작: {strategy.get('name', fname)}")
        return {"ok": True}
    except Exception as e:
        log(f"자동매매 시작 실패: {e}")
        STATE.current_strategy_info = None
        return JSONResponse({"error": f"자동매매 시작 실패: {str(e)}"}, status_code=500)

@app.post("/api/autopilot/stop")
async def api_autopilot_stop():
    if STATE.autobot and STATE.autobot.is_running():
        await STATE.autobot.stop()
        push_system("자동매매 중지")
        push_auto_status("===== 자동매매 중지됨 =====")
        STATE.current_strategy_info = None
    return {"ok": True}

@app.get("/api/autopilot/status")
def api_autopilot_status():
    return {
        "lines": STATE.auto_status_lines, 
        "running": STATE.autobot.is_running() if STATE.autobot else False,
        "strategy_info": STATE.current_strategy_info
    }

# ------------------------ 터미널(WebSocket) ------------------------
class TerminalSession:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.history: List[str] = []
        self.pending: Optional[Dict[str, Any]] = None
        self.last_symbol: Optional[str] = None

    async def send(self, s: str):
        try:
            await self.ws.send_text(s)
        except:
            pass

    async def handle(self, raw: str):
        # Space 키를 Enter로 처리
        if raw == ' ' and self.pending:
            raw = ''
        
        raw = raw.strip()
        
        # 대화형 모드에서 빈 입력 처리
        if self.pending and raw == '':
            await self._handle_pending(raw)
            return
        
        if not raw:
            return
        
        self.history.append(raw)
        self.history = self.history[-20:]  # 최근 20개로 증가

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
            elif cmd == 'myetf':
                await self._cmd_list_myetf()
            elif cmd == 'positions' or cmd == 'pos':
                await self._cmd_positions()
            elif cmd.startswith('.'):  # .TICKER
                await self._cmd_ticker(cmd[1:])
            else:
                await self.send("❌ 알 수 없는 명령입니다. 'help'를 입력해 도움말을 보세요.")
        except Exception as e:
            await self.send(f"❌ 오류: {e}")
            log(f"터미널 명령 오류: {traceback.format_exc()}")

    async def _cmd_help(self):
        help_text = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                     Wealth Commander 터미널 도움말                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ 📊 정보 조회 명령어                                                          ║
║──────────────────────────────────────────────────────────────────────────────║
║  .TICKER              종목 정보 조회 (예: .SOXL)                             ║
║  positions (pos)      보유 포지션 조회                                       ║
║  orders               미체결 주문 목록                                       ║
║  history              체결 이력 (최근)                                       ║
║  myetf                myETF 목록 조회                                        ║
║                                                                              ║
║ 💰 매매 주문 명령어                                                          ║
║──────────────────────────────────────────────────────────────────────────────║
║  buy [대화형/인자]    매수 주문                                              ║
║    - buy .SOXL 20     : 20주 매수                                           ║
║    - buy .SOXL 20%    : Buying Power의 20% 매수                            ║
║    - buy .SOXL $20    : 20달러어치 매수                                     ║
║    - buy myTECH_01 $1000 : myETF 비중대로 배분                             ║
║  sell [대화형/인자]   매도 주문                                              ║
║                                                                              ║
║ 🚫 주문 관리 명령어                                                          ║
║──────────────────────────────────────────────────────────────────────────────║
║  cancel [주문ID|all]  주문 취소 (대화형/직접)                                ║
║                                                                              ║
║ 💡 사용 팁                                                                   ║
║──────────────────────────────────────────────────────────────────────────────║
║  • 대화형 모드 중 'exit' 입력으로 취소 가능                                  ║
║  • ↑↓ 화살표로 명령 히스토리 탐색                                          ║
║  • Ctrl+L: 터미널 클리어                                                     ║
║  • Ctrl+H: 도움말 표시                                                       ║
║  • Enter 입력이 필요한 곳에서 Space 키도 Enter로 인식                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """
        await self.send(help_text.strip())

    async def _cmd_positions(self):
        """보유 포지션 조회 - 테이블 형식 개선"""
        client = get_client()
        positions = client.list_positions()
        
        if not positions:
            await self.send("보유 포지션이 없습니다.")
            return
        
        # 헤더
        header = "╔════════════════════════════════════════════════════════════════════════╗\n"
        header += "║                           보유 포지션                                  ║\n"
        header += "╠════════╤═══════════╤═══════════╤═══════════╤════════════╤════════════╣\n"
        header += "║ 종목   │    수량   │   평단가  │   현재가  │    평가액  │    손익    ║\n"
        header += "╠════════╪═══════════╪═══════════╪═══════════╪════════════╪════════════╣"
        
        await self.send(header)
        
        total_value = 0
        total_pl = 0
        
        for pos in positions:
            symbol = pos.get('symbol', '')
            qty = float(pos.get('qty', 0))
            avg_price = float(pos.get('avg_entry_price', 0))
            current_price = float(pos.get('current_price', 0))
            market_value = float(pos.get('market_value', 0))
            unrealized_pl = float(pos.get('unrealized_pl', 0))
            pl_pct = float(pos.get('unrealized_plpc', 0)) * 100
            
            total_value += market_value
            total_pl += unrealized_pl
            
            # 색상 표시 (미국식: 상승 녹색, 하락 적색)
            pl_symbol = '+' if unrealized_pl >= 0 else ''
            color = '🟢' if unrealized_pl >= 0 else '🔴'
            
            # 테이블 행 출력
            row = f"║ {symbol:<6} │ {qty:>9.2f} │ ${avg_price:>8.2f} │ ${current_price:>8.2f} │ "
            row += f"${market_value:>9,.2f} │ {color} {pl_symbol}${abs(unrealized_pl):>7,.2f} ║"
            await self.send(row)
        
        # 합계
        footer = "╠════════╧═══════════╧═══════════╧═══════════╧════════════╪════════════╣\n"
        pl_symbol = '+' if total_pl >= 0 else ''
        color = '🟢' if total_pl >= 0 else '🔴'
        footer += f"║ 총 평가액: ${total_value:>15,.2f}                     │ {color} {pl_symbol}${abs(total_pl):>9,.2f} ║\n"
        footer += "╚═══════════════════════════════════════════════════════════╧════════════╝"
        
        await self.send(footer)

    async def _cmd_list_myetf(self):
        """myETF 목록 표시 - 테이블 형식"""
        myetf_files = list_myetf_files()
        
        if not myetf_files:
            await self.send("등록된 myETF가 없습니다.")
            await self.send(f"(경로: {MYETF_DIR})")
            return
        
        header = "╔══════════════════════════════════════════════════════════════════╗\n"
        header += "║                         myETF 목록                               ║\n"
        header += "╠═══════════════════╤═══════════════════════════════════════════════╣"
        
        await self.send(header)
        
        for name in myetf_files:
            valid, data, error = validate_myetf(name)
            
            if valid and data:
                assets = data.get('assets', [])
                symbols = [f"{a['symbol'].lstrip('.')}({a['weight']}%)" for a in assets[:3]]
                symbols_str = ', '.join(symbols)
                if len(assets) > 3:
                    symbols_str += f" 외 {len(assets)-3}개"
                
                await self.send(f"║ ✅ {name:<14} │ {symbols_str:<45} ║")
            else:
                await self.send(f"║ ❌ {name:<14} │ {error:<45} ║")
        
        footer = "╠═══════════════════╧═══════════════════════════════════════════════╣\n"
        footer += f"║ 총 {len(myetf_files)}개 myETF │ 사용법: buy {{name}} $금액                       ║\n"
        footer += "╚══════════════════════════════════════════════════════════════════╝"
        
        await self.send(footer)

    async def _cmd_orders(self):
        """미체결 주문 목록 - 번호 표시, 테이블 형식"""
        client = get_client()
        orders = client.list_orders(status='open', limit=50)
        
        if not orders:
            await self.send("열린 주문이 없습니다.")
            return
        
        header = "╔════════════════════════════════════════════════════════════════════════╗\n"
        header += "║                            Open Orders                                ║\n"
        header += "╠═══╤═══════╤══════╤═══════╤═══════════╤════════════╤══════════════════╣\n"
        header += "║ # │ 종목  │ 구분 │  수량 │   가격    │    상태    │      시간        ║\n"
        header += "╠═══╪═══════╪══════╪═══════╪═══════════╪════════════╪══════════════════╣"
        
        await self.send(header)
        await self._show_numbered_orders(orders)
        
        footer = "╠═══╧═══════╧══════╧═══════╧═══════════╧════════════╧══════════════════╣\n"
        footer += f"║ 총 {len(orders)}개 주문 │ 'cancel' 명령으로 취소 가능                              ║\n"
        footer += "╚════════════════════════════════════════════════════════════════════════╝"
        
        await self.send(footer)

    async def _show_numbered_orders(self, orders: List[Dict[str, Any]]):
        """번호가 매겨진 주문 목록 표시 - 테이블 형식"""
        for i, o in enumerate(orders, 1):
            order_id = o.get('id', '')[:8]
            symbol = o.get('symbol', '')
            side = o.get('side', '').upper()[:3]
            qty = float(o.get('qty', '0'))
            order_type = o.get('order_type', 'limit')
            limit_price = o.get('limit_price')
            
            if order_type == 'limit' and limit_price:
                price_str = f"${float(limit_price):>8.2f}"
            else:
                price_str = "  MARKET "
            
            status = o.get('status', '')[:10]
            filled_qty = o.get('filled_qty', '0')
            
            # 시간 정보 (미국식)
            created_at = o.get('created_at', '')
            if created_at:
                dt = datetime.datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                time_str = dt.strftime("%m/%d %I:%M%p")
            else:
                time_str = ""
            
            # 부분 체결 표시
            if float(filled_qty) > 0:
                status = f"{status}*"
            
            row = f"║{i:2} │ {symbol:<5} │ {side:<4} │{qty:>6.2f} │ {price_str} │ {status:<10} │ {time_str:<16} ║"
            await self.send(row)

    async def _cmd_history(self):
        """체결 이력 - 테이블 형식"""
        client = get_client()
        acts = client.get_activities(activity_types='FILL', page_size=50)
        if not acts:
            await self.send("최근 체결 이력이 없습니다.")
            return
        
        header = "╔═══════════════════════════════════════════════════════════════════════╗\n"
        header += "║                          Recent Fills                                 ║\n"
        header += "╠══════════════════╤═══════╤══════╤═══════╤════════════════════════════╣\n"
        header += "║       시간       │ 종목  │ 구분 │  수량 │         가격               ║\n"
        header += "╠══════════════════╪═══════╪══════╪═══════╪════════════════════════════╣"
        
        await self.send(header)
        
        for a in acts[:10]:
            trans_time = a.get('transaction_time', '')
            if trans_time:
                dt = datetime.datetime.fromisoformat(trans_time.replace('Z', '+00:00'))
                time_str = dt.strftime("%m/%d %I:%M:%S%p")
            else:
                time_str = ""
            
            symbol = a.get('symbol', '')
            side = a.get('side', '').upper()[:3]
            qty = float(a.get('qty', '0'))
            price = float(a.get('price', '0'))
            
            row = f"║ {time_str:<16} │ {symbol:<5} │ {side:<4} │{qty:>6.2f} │ ${price:>8.2f}              ║"
            await self.send(row)
        
        footer = "╚══════════════════╧═══════╧══════╧═══════╧════════════════════════════╝"
        await self.send(footer)

    async def _cmd_cancel(self, args: List[str]):
        """주문 취소 - 대화형/직접 취소"""
        client = get_client()
        
        if not args:
            # 대화형 취소 시작
            orders = client.list_orders(status='open', limit=50)
            if not orders:
                await self.send("❌ 취소할 주문이 없습니다.")
                return
            
            await self.send("╔════════════════════════════════════════════╗")
            await self.send("║              주문 취소                     ║")
            await self.send("╚════════════════════════════════════════════╝")
            await self._show_numbered_orders(orders)
            await self.send("────────────────────────────────────────────")
            await self.send("취소할 주문 번호를 입력하세요")
            await self.send("(all = 전체 취소, exit = 취소):")
            
            self.pending = {"flow": "cancel", "step": "select", "orders": orders}
            return
        
        target = args[0].lower()
        if target == 'all':
            await self._cancel_all_orders()
        else:
            # 주문 ID로 직접 취소
            ok = client.cancel_order(target)
            await self.send("✅ 취소 요청 완료." if ok else "❌ 취소 실패 또는 이미 취소됨.")

    async def _cancel_all_orders(self):
        """모든 주문 취소"""
        client = get_client()
        orders = client.list_orders(status='open')
        
        if not orders:
            await self.send("❌ 취소할 주문이 없습니다.")
            return
        
        success_count = 0
        fail_count = 0
        
        await self.send(f"🔄 {len(orders)}개 주문 취소 중...")
        
        for o in orders:
            order_id = o.get('id', '')
            symbol = o.get('symbol', '')
            
            if client.cancel_order(order_id):
                success_count += 1
                await self.send(f"  ✅ {symbol} 주문 취소됨")
            else:
                fail_count += 1
                await self.send(f"  ❌ {symbol} 주문 취소 실패")
        
        await self.send(f"완료: 성공 {success_count}개, 실패 {fail_count}개")

    async def _cmd_ticker(self, sym: str):
        """티커 정보 조회 - 개선된 포맷"""
        client = get_client()
        
        # 심볼 정규화: .SOXL -> SOXL
        sym = sym.upper().lstrip('.')
        if not sym:
            await self.send("❌ 올바른 심볼을 입력하세요.")
            return
        
        self.last_symbol = sym
        
        try:
            # 시세 조회
            last = client.get_latest_trade(sym)
            if last is None or last == 0:
                await self.send(f"❌ {sym} 시세를 조회할 수 없습니다.")
                return
            
            # 일봉 데이터
            dailies = client.get_daily_ohlc(sym, limit=2) or []
            o = h = l = c = prev_c = None
            change = change_pct = 0.0
            
            if len(dailies) >= 1:
                curr_day = dailies[-1]
                o, h, l, c = curr_day.get('o'), curr_day.get('h'), curr_day.get('l'), curr_day.get('c')
                
                if len(dailies) >= 2:
                    prev_day = dailies[-2]
                    prev_c = prev_day.get('c')
                    
                    if prev_c and prev_c > 0:
                        change = last - prev_c
                        change_pct = (change / prev_c) * 100
            
            # 포지션 정보
            positions = client.list_positions()
            pos = next((p for p in positions if p.get('symbol') == sym), None)
            
            # 출력 포맷 - 테이블 형식
            header = f"╔{'═' * 60}╗\n"
            header += f"║{sym:^60}║\n"
            header += f"╠{'═' * 60}╣"
            await self.send(header)
            
            # 현재가 정보 (미국식 색상)
            color = '🟢' if change >= 0 else '🔴'
            pl_symbol = '+' if change >= 0 else ''
            
            await self.send(f"║ 현재가: ${last:>10,.2f}   {color} {pl_symbol}{change:>8.2f} ({pl_symbol}{change_pct:>6.2f}%)       ║")
            
            if o and h and l and c:
                await self.send(f"║ 일봉: O:${o:.2f}  H:${h:.2f}  L:${l:.2f}  C:${c:.2f}          ║")
            
            await self.send(f"╠{'═' * 60}╣")
            
            if pos:
                qty = float(pos.get('qty', 0))
                avg_price = float(pos.get('avg_entry_price', 0))
                market_value = float(pos.get('market_value', 0))
                unrealized_pl = float(pos.get('unrealized_pl', 0))
                pl_pct = (unrealized_pl / (qty * avg_price)) * 100 if qty * avg_price > 0 else 0
                
                pl_color = '🟢' if unrealized_pl >= 0 else '🔴'
                pl_symbol = '+' if unrealized_pl >= 0 else ''
                
                await self.send(f"║ 보유: {qty:>10.4f}주    평단: ${avg_price:>10,.2f}              ║")
                await self.send(f"║ 평가: ${market_value:>10,.2f}    손익: {pl_color} {pl_symbol}${abs(unrealized_pl):>8,.2f} ({pl_symbol}{pl_pct:.2f}%) ║")
            else:
                await self.send(f"║ 보유: 없음                                               ║")
            
            footer = f"╚{'═' * 60}╝"
            await self.send(footer)
            
        except Exception as e:
            await self.send(f"❌ 조회 실패: {str(e)}")
            log(f"티커 조회 오류 {sym}: {traceback.format_exc()}")

    async def _cmd_buy(self, args: List[str]):
        if not args:
            # 대화형 시작
            await self.send("╔════════════════════════════════════════════╗")
            await self.send("║              매수 주문                     ║")
            await self.send("╚════════════════════════════════════════════╝")
            await self.send("종목(.TICKER) 또는 myETF 이름을 입력하세요:")
            await self.send("예: .SOXL 또는 myTECH_01")
            
            # myETF 목록 표시
            myetf_files = list_myetf_files()
            if myetf_files:
                await self.send(f"사용 가능한 myETF: {', '.join(myetf_files)}")
            
            self.pending = {"flow": "buy", "step": "symbol"}
            return

        # 인자 해석
        await self._process_buy_sell_args(flow='buy', args=args)

    async def _cmd_sell(self, args: List[str]):
        # sell all 처리 추가
        if args and args[0].lower() == 'all':
            await self._sell_all_positions()
            return
            
        if not args:
            await self.send("╔════════════════════════════════════════════╗")
            await self.send("║              매도 주문                     ║")
            await self.send("╚════════════════════════════════════════════╝")
            await self.send("종목(.TICKER) 또는 myETF 이름을 입력하세요:")
            await self.send("예: .SOXL 또는 myTECH_01")
            await self.send("(all = 전체 보유 종목 매도)")
            self.pending = {"flow": "sell", "step": "symbol"}
            return

        await self._process_buy_sell_args(flow='sell', args=args)
    async def _sell_all_positions(self):
        """전체 보유 종목 매도"""
        client = get_client()
        positions = client.list_positions()
        
        if not positions:
            await self.send("❌ 보유 종목이 없습니다.")
            return
        
        # 예상 수익금 계산
        total_value = sum(float(p.get('market_value', 0)) for p in positions)
        total_pl = sum(float(p.get('unrealized_pl', 0)) for p in positions)
        
        await self.send("╔════════════════════════════════════════════╗")
        await self.send("║           전체 포지션 매도                 ║")
        await self.send("╠════════════════════════════════════════════╣")
        await self.send(f"║ 보유 종목: {len(positions)}개                           ║")
        await self.send(f"║ 총 평가액: ${total_value:>15,.2f}             ║")
        
        pl_color = '🟢' if total_pl >= 0 else '🔴'
        pl_symbol = '+' if total_pl >= 0 else ''
        await self.send(f"║ 예상 손익: {pl_color} {pl_symbol}${abs(total_pl):>13,.2f}         ║")
        await self.send("╠════════════════════════════════════════════╣")
        await self.send("║ 종목별 내역:                              ║")
        
        for pos in positions:
            symbol = pos.get('symbol', '')
            qty = float(pos.get('qty', 0))
            market_value = float(pos.get('market_value', 0))
            unrealized_pl = float(pos.get('unrealized_pl', 0))
            current_price = float(pos.get('current_price', 0))
            
            pl_symbol = '+' if unrealized_pl >= 0 else ''
            await self.send(f"║ {symbol:<6}: {qty:>8.4f}주 @ ${current_price:>7.2f} = ${market_value:>10,.2f} ║")
        
        await self.send("╚════════════════════════════════════════════╝")
        await self.send(f"매도 시 예상 수령액: ${total_value:,.2f}")
        await self.send("진행하시겠습니까? (Y/N):")
        
        self.pending = {"flow": "sell_all", "step": "confirm", "positions": positions}

    async def _process_buy_sell_args(self, flow: str, args: List[str]):
        sym_or_etf = args[0]
        limit_price: Optional[float] = None
        size_token: Optional[str] = None
        
        if len(args) >= 2:
            size_token = args[1]
        
        if len(args) >= 3:
            try:
                limit_price = float(args[2].replace('$',''))
            except:
                limit_price = None

        # 심볼 검증
        if sym_or_etf.startswith('.'):
            # 일반 종목
            await self._execute_order(flow, sym_or_etf, size_token, limit_price)
        elif not sym_or_etf.startswith('.'):
            # myETF 체크
            valid, data, error = validate_myetf(sym_or_etf)
            if valid:
                await self._execute_order(flow, sym_or_etf, size_token, limit_price)
            else:
                await self.send(f"❌ myETF 오류: {error}")
        else:
            await self.send("❌ 종목은 .TICKER 또는 myETF 형식으로 입력하세요.")

    async def _handle_pending(self, user_input: str):
        """대화형 입력 처리 - Space를 Enter로 처리"""
        flow = self.pending.get('flow')
        step = self.pending.get('step')
        
        # 취소 명령
        if user_input.lower() in ('exit', 'quit', 'esc', 'cancel'):
            await self.send("⚠️ 취소됨")
            self.pending = None
            return
        
        if flow == 'cancel':
            await self._handle_pending_cancel(step, user_input)
        elif flow in ('buy', 'sell'):
            await self._handle_pending_buy_sell(flow, step, user_input)

    async def _handle_pending_cancel(self, step: str, user_input: str):
        """cancel 대화형 처리"""
        if step == 'select':
            orders = self.pending.get('orders', [])
            choice = user_input.strip().lower()
            
            if choice == 'all':
                await self._cancel_all_orders()
                self.pending = None
                return
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(orders):
                    order = orders[idx]
                    order_id = order.get('id', '')
                    symbol = order.get('symbol', '')
                    
                    client = get_client()
                    if client.cancel_order(order_id):
                        await self.send(f"✅ {symbol} 주문 취소 완료")
                    else:
                        await self.send(f"❌ {symbol} 주문 취소 실패")
                else:
                    await self.send(f"❌ 잘못된 번호입니다. 1-{len(orders)} 사이를 선택하세요.")
                    return
            except ValueError:
                await self.send("❌ 숫자 또는 'all'을 입력하세요.")
                return
            
            self.pending = None

    async def _handle_pending_buy_sell(self, flow: str, step: str, user_input: str):
        client = get_client()
        
        # sell all 확인 처리
        if flow == 'sell_all' and step == 'confirm':
            yn = user_input.strip().lower()
            if yn in ('y', 'yes', 'ok', 'ㅛ'):
                positions = self.pending.get('positions', [])
                await self.send("╔════════════════════════════════════════════╗")
                await self.send("║         전체 포지션 매도 실행              ║")
                await self.send("╚════════════════════════════════════════════╝")
                
                success_count = 0
                fail_count = 0
                
                for pos in positions:
                    symbol = pos.get('symbol', '')
                    qty = float(pos.get('qty', 0))
                    current_price = float(pos.get('current_price', 0))
                    
                    resp = client.submit_order(
                        symbol=symbol,
                        side='sell',
                        qty=qty,
                        type_='limit',
                        time_in_force='day',
                        limit_price=current_price,
                        extended_hours=STATE.extended_hours
                    )
                    
                    if 'error' not in resp:
                        success_count += 1
                        await self.send(f"✅ {symbol}: {qty:.4f}주 @ ${current_price:,.2f}")
                    else:
                        fail_count += 1
                        await self.send(f"❌ {symbol}: 매도 실패")
                
                await self.send("────────────────────────────────────────────")
                await self.send(f"완료: 성공 {success_count}개, 실패 {fail_count}개")
            else:
                await self.send("⚠️ 전체 매도가 취소되었습니다.")
            
            self.pending = None
            return
        
        if step == 'symbol':
            target = user_input.strip()
            
            # "all" 입력 처리
            if target.lower() == 'all':
                await self._sell_all_positions()
                self.pending = None
                return
            
            # 심볼 검증
            if target.startswith('.'):
                # 일반 종목 검증
                sym = target[1:].upper()
                if not sym:
                    await self.send("❌ 올바른 종목 심볼을 입력하세요.")
                    await self.send("다시 입력하세요:")
                    return
                
                # 현재가 표시
                last = client.get_latest_trade(sym)
                if last is None or last == 0:
                    await self.send(f"❌ {sym} 시세를 조회할 수 없습니다.")
                    await self.send("다른 종목을 입력하세요:")
                    return
                
                await self.send(f"💵 현재가: ${last:,.2f}")
                self.pending['target'] = target
                self.pending['is_myetf'] = False
                
            else:
                # myETF 검증
                valid, data, error = validate_myetf(target)
                if not valid:
                    await self.send(f"❌ {error}")
                    
                    # 사용 가능한 myETF 목록 표시 (.json 제거)
                    myetf_files = list_myetf_files()
                    if myetf_files:
                        clean_names = [f.replace('.json', '') for f in myetf_files]
                        await self.send(f"사용 가능한 myETF: {', '.join(clean_names)}")
                    
                    await self.send("다시 입력하세요:")
                    return
                
                self.pending['target'] = target
                self.pending['is_myetf'] = True
                self.pending['myetf_data'] = data
            
            # 보유 상태 표시
            await self._print_holding_state(self.pending['target'])
            
            # 다음 단계
            if self.pending.get('is_myetf'):
                if flow == 'sell':
                    await self.send("매도할 금액($) 또는 비율(%)를 입력하세요:")
                else:
                    await self.send("투자 금액($) 또는 비율(%)를 입력하세요:")
                await self.send("예: $1000 | 25%")
            else:
                # 현재가 다시 표시
                if target.startswith('.'):
                    sym = target[1:].upper()
                    last = client.get_latest_trade(sym)
                    if last:
                        await self.send(f"💵 현재가: ${last:,.2f}")
                
                await self.send("수량, 금액($), 또는 비율(%)를 입력하세요:")
                await self.send("예: 20 | $100 | 25%")
            
            self.pending['step'] = 'size'
            return
        
        if step == 'size':
            size_token = user_input.strip()
            
            # 크기 검증
            try:
                mode, val = parse_size_token(size_token)
                
                # myETF는 수량 불가
                if self.pending.get('is_myetf') and mode == 'shares':
                    await self.send("❌ myETF는 금액($) 또는 비율(%)만 입력 가능합니다.")
                    await self.send("다시 입력하세요:")
                    return
                
                if val <= 0:
                    await self.send("❌ 0보다 큰 값을 입력하세요.")
                    await self.send("다시 입력하세요:")
                    return
                
                self.pending['size_token'] = size_token
                
            except ValueError:
                await self.send("❌ 올바른 형식으로 입력하세요.")
                await self.send("예: 20 | $100 | 25%")
                await self.send("다시 입력하세요:")
                return
            
            # myETF는 목표가 불필요
            if self.pending.get('is_myetf'):
                await self._confirm_pending_order(flow)
                self.pending['step'] = 'confirm'
            else:
                # 현재가 표시
                target = self.pending.get('target')
                if target and target.startswith('.'):
                    sym = target[1:].upper()
                    last = client.get_latest_trade(sym)
                    if last:
                        await self.send(f"💵 현재가: ${last:,.2f}")
                
                await self.send("목표 가격을 입력하세요 (Enter 또는 Space로 현재가 사용):")
                self.pending['step'] = 'price'
            return
    async def _print_holding_state(self, sym_or_etf: str):
        client = get_client()
        if sym_or_etf.startswith('.'):
            sym = sym_or_etf[1:].upper()
            positions = client.list_positions()
            pos = next((p for p in positions if p.get('symbol') == sym), None)
            
            if pos:
                qty = float(pos.get('qty', 0))
                market_value = float(pos.get('market_value', 0))
                avg_price = float(pos.get('avg_entry_price', 0))
                await self.send(f"📊 현재 보유: {qty:.4f}주 @ ${avg_price:,.2f} (${market_value:,.2f})")
            else:
                await self.send("📊 현재 보유: 없음")
        else:
            # myETF 구성 종목 보유 현황
            valid, data, _ = validate_myetf(sym_or_etf)
            if valid and data:
                await self.send(f"📊 myETF: {data.get('name', sym_or_etf)}")
                assets = data.get('assets', [])
                await self.send(f"구성: {len(assets)}개 종목")

    async def _confirm_pending_order(self, flow: str):
        target = self.pending.get('target')
        size_token = self.pending.get('size_token')
        limit_price = self.pending.get('limit_price')
        client = get_client()

        if target.startswith('.'):
            sym = target[1:].upper()
            last = client.get_latest_trade(sym) or 0.0
            price = limit_price if limit_price is not None else last
            
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
            
            await self.send("╔════════════════════════════════════════════╗")
            await self.send("║              주문 확인                     ║")
            await self.send("╠════════════════════════════════════════════╣")
            await self.send(f"║ 종목: {sym:<37} ║")
            await self.send(f"║ 구분: {side:<37} ║")
            await self.send(f"║ 수량: {qty:>10.4f}주                          ║")
            await self.send(f"║ 가격: ${price:>10,.2f} {'(현재가)' if limit_price is None else '(지정가)':<18} ║")
            
            if flow == 'sell':
                await self.send(f"║ 예상 수령액: ${total:>10,.2f}                  ║")
            else:
                await self.send(f"║ 총액: ${total:>10,.2f}                       ║")
            
            await self.send("╚════════════════════════════════════════════╝")
            await self.send("진행하시겠습니까? (Y/N):")
            
        else:
            # myETF 처리
            data = self.pending.get('myetf_data')
            if not data:
                valid, data, error = validate_myetf(target)
                if not valid:
                    await self.send(f"❌ {error}")
                    return
            
            acc = client.get_account()
            bp = float(acc.get('buying_power', '0'))
            
            mode, val = parse_size_token(size_token)
            if mode == 'percent':
                notional = bp * (val / 100.0)
            elif mode == 'notional':
                notional = val
            else:
                await self.send("❌ myETF는 금액($) 또는 비율(%)만 입력 가능합니다.")
                return
            
            await self.send("╔════════════════════════════════════════════╗")
            await self.send("║           myETF 주문 확인                  ║")
            await self.send("╠════════════════════════════════════════════╣")
            await self.send(f"║ myETF: {data.get('name', target):<36} ║")
            await self.send(f"║ 구분: {'매수' if flow=='buy' else '매도':<37} ║")
            
            if flow == 'sell':
                await self.send(f"║ 매도 금액: ${notional:>10,.2f}                    ║")
            else:
                await self.send(f"║ 총 투자금액: ${notional:>10,.2f}                  ║")
            
            # 구성 종목 표시
            assets = data.get('assets', [])
            await self.send("╠════════════════════════════════════════════╣")
            await self.send(f"║ 구성 종목 ({len(assets)}개):                            ║")
            for a in assets:
                sym = a['symbol'].lstrip('.')
                weight = a['weight']
                alloc = notional * (weight / 100.0)
                await self.send(f"║   - {sym:<6}: {weight:>5.2f}% (약 ${alloc:>8,.2f})          ║")
            
            await self.send("╚════════════════════════════════════════════╝")
            await self.send("진행하시겠습니까? (Y/N):")


    async def _execute_order(self, flow: str, sym_or_etf: str, size_token: Optional[str], limit_price: Optional[float]):
        client = get_client()
        side = 'buy' if flow=='buy' else 'sell'

        if sym_or_etf.startswith('.'):
            # 일반 종목 주문
            sym = sym_or_etf[1:].upper()
            last = client.get_latest_trade(sym) or 0.0
            price = limit_price if limit_price is not None else last
            
            acc = client.get_account()
            bp = float(acc.get('buying_power', '0'))
            
            if size_token is None:
                await self.send("❌ 수량/금액/비율이 없습니다.")
                return
            
            mode, val = parse_size_token(size_token)
            if mode == 'percent':
                qty = compute_from_percent(bp, val, price)
            elif mode == 'notional':
                qty = compute_from_notional(val, price)
            else:
                qty = float(val)

            if qty <= 0:
                await self.send("❌ 주문 수량이 0입니다.")
                return

            # 잔고 확인 (매도 시)
            if side == 'sell':
                positions = client.list_positions()
                pos = next((p for p in positions if p.get('symbol') == sym), None)
                if not pos:
                    await self.send(f"❌ {sym} 보유 수량이 없습니다.")
                    return
                
                held_qty = float(pos.get('qty', 0))
                if qty > held_qty:
                    await self.send(f"❌ 보유 수량({held_qty:.4f})보다 많이 매도할 수 없습니다.")
                    return

            resp = client.submit_order(
                symbol=sym, 
                side=side, 
                qty=qty, 
                type_='limit',
                time_in_force='day', 
                limit_price=price,
                extended_hours=STATE.extended_hours
            )
            
            if 'error' in resp:
                error_msg = resp['error'].get('message', str(resp['error'])) if isinstance(resp['error'], dict) else str(resp['error'])
                await self.send(f"❌ 주문 실패: {error_msg}")
            else:
                order_id = resp.get('id', '')[:8]
                await self.send(f"✅ 주문 제출 완료!")
                await self.send(f"주문 ID: {order_id}")
                await self.send(f"{sym} {side.upper()} {qty:.4f}주 @ ${price:,.2f}")
            return

        # myETF 처리
        valid, data, error = validate_myetf(sym_or_etf)
        if not valid:
            await self.send(f"❌ myETF 오류: {error}")
            return
        
        assets = data.get('assets', [])
        acc = client.get_account()
        bp = float(acc.get('buying_power', '0'))
        
        if size_token is None:
            await self.send("❌ 금액($) 또는 비율(%)을 입력하세요.")
            return
        
        mode, val = parse_size_token(size_token)
        if mode == 'percent':
            total_notional = bp * (val / 100.0)
        elif mode == 'notional':
            total_notional = val
        else:
            await self.send("❌ myETF는 금액($) 또는 비율(%)만 허용됩니다.")
            return

        # 비중 배분하여 각 심볼 주문
        await self.send("╔════════════════════════════════════════════╗")
        await self.send("║           myETF 주문 실행                  ║")
        await self.send("╚════════════════════════════════════════════╝")
        success_count = 0
        fail_count = 0
        skip_count = 0  # 스킵 카운트 추가
        
        for a in assets:
            sym = a['symbol'].lstrip('.').upper()
            w = float(a['weight']) / 100.0
            alloc = total_notional * w
            
            last = client.get_latest_trade(sym) or 0.0
            if last <= 0:
                await self.send(f"❌ {sym}: 가격 조회 실패")
                fail_count += 1
                continue
            
            qty = compute_from_notional(alloc, last)
            if qty <= 0.0001:  # Alpaca 최소 수량
                await self.send(f"⚠️ {sym}: 수량 너무 작음 (스킵)")
                skip_count += 1
                continue
            
            # 매도 시 보유 수량 체크
            if side == 'sell':
                positions = client.list_positions()
                pos = next((p for p in positions if p.get('symbol') == sym), None)
                if not pos:
                    await self.send(f"⚠️ {sym}: 미보유 (스킵)")
                    skip_count += 1
                    continue
                
                held_qty = float(pos.get('qty', 0))
                if qty > held_qty:
                    qty = held_qty  # 보유 수량만큼만 매도
            
            resp = client.submit_order(
                symbol=sym, 
                side=side, 
                qty=qty, 
                type_='limit',
                time_in_force='day', 
                limit_price=last,
                extended_hours=STATE.extended_hours
            )
            
            if 'error' not in resp:
                success_count += 1
                await self.send(f"✅ {sym}: {qty:.4f}주 @ ${last:,.2f}")
            else:
                fail_count += 1
                error_msg = resp['error'].get('message', 'Unknown') if isinstance(resp['error'], dict) else str(resp['error'])
                await self.send(f"❌ {sym}: {error_msg}")
        
        await self.send("────────────────────────────────────────────")
        if skip_count > 0:
            await self.send(f"완료: 성공 {success_count}개, 실패 {fail_count}개, 스킵 {skip_count}개")
        else:
            await self.send(f"완료: 성공 {success_count}개, 실패 {fail_count}개")

sessions: Dict[str, TerminalSession] = {}

@app.websocket("/ws/terminal")
async def ws_terminal(ws: WebSocket):
    await ws.accept()
    STATE.websockets.append(ws)
    
    sid = str(id(ws))
    sess = TerminalSession(ws)
    sessions[sid] = sess
    
    await sess.send("🚀 Wealth Commander 터미널 v0.2.1")
    await sess.send("'help'를 입력하여 사용법을 확인하세요.")
    
    try:
        while True:
            msg = await ws.receive_text()
            await sess.handle(msg)
    except WebSocketDisconnect:
        sessions.pop(sid, None)
        if ws in STATE.websockets:
            STATE.websockets.remove(ws)
    except Exception as e:
        log(f"WebSocket 오류: {e}")
        sessions.pop(sid, None)
        if ws in STATE.websockets:
            STATE.websockets.remove(ws)

# 앱 시작 시 초기화
@app.on_event("startup")
async def startup_event():
    log("Wealth Commander 시작")
    push_system("시스템 초기화 완료 v0.2.1")

@app.on_event("shutdown")
async def shutdown_event():
    if STATE.autobot and STATE.autobot.is_running():
        await STATE.autobot.stop()
    log("Wealth Commander 종료")