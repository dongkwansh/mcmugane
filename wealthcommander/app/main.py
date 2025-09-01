# app/main.py
import logging
import json
import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel  # <--- 'pantic' 오타 수정

from app.config import (load_settings, save_settings, list_strategies, Settings, 
                        get_market_colors, get_market_status)
from app.logging_setup import setup_logging
from app.alpaca_client import AlpacaBroker
from app.strategies.runner import StrategyRunner
from app.terminal.session import TerminalSessionManager

# --- 전역 변수 ---
settings: Settings
broker: AlpacaBroker
runner: StrategyRunner
sched: AsyncIOScheduler
terminal_mgr: TerminalSessionManager
manager: "ConnectionManager"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- WebSocket 연결 관리 ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except (WebSocketDisconnect, RuntimeError):
                self.disconnect(connection)

# --- 애플리케이션 생명주기 (Lifespan) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작 및 종료 이벤트를 처리합니다."""
    global settings, broker, runner, sched, terminal_mgr, manager

    # --- 시작 ---
    manager = ConnectionManager()
    settings = load_settings()
    setup_logging(log_dir="logs")
    
    broker = AlpacaBroker(settings)
    runner = StrategyRunner(broker, settings)
    
    sched = AsyncIOScheduler(timezone=settings.timezone)
    sched.add_job(
        runner.tick, "interval", 
        seconds=settings.auto.interval_seconds, id="auto_trade_job"
    )
    
    # 터미널 매니저는 스케줄러가 설정된 후에 생성
    terminal_mgr = TerminalSessionManager(
        broker, runner, settings,
        scheduler=sched,
        on_state_change=broadcast_status_update
    )
    
    # 모든 설정이 끝난 후 스케줄러 시작
    sched.start(paused=not settings.auto.enabled)
    
    is_paused = sched.get_job('auto_trade_job').next_run_time is None
    logging.getLogger("init").info(f"시스템 초기화 완료. 계정: {settings.current_account}, 자동매매 시작 상태: {'일시중지' if is_paused else '실행중'}")
    
    yield

    # --- 종료 ---
    if sched.running:
        sched.shutdown()
    logging.getLogger("shutdown").info("시스템이 종료되었습니다.")

# --- FastAPI 앱 초기화 ---
app = FastAPI(lifespan=lifespan, title="WealthCommander Trading System")

# --- API 요청 모델 ---
class AutoRequest(BaseModel):
    enabled: bool
    strategy: Optional[str] = None
    interval_seconds: Optional[int] = None

# --- 유틸리티 함수 ---
def get_current_status_payload() -> dict:
    """프론트엔드로 보낼 현재 시스템 상태 페이로드를 생성합니다."""
    return {
        "mode": settings.mode, "auto": settings.auto.model_dump(),
        "strategy": settings.auto.strategy, "strategies": list_strategies(),
        "alpaca": "OK" if broker.enabled else "NO-CREDS",
        "buying_power": broker.buying_power() if broker.enabled else 0,
        "language": settings.language, "colors": settings.colors,
        "market": get_market_status(), "current_account": settings.current_account,
        "accounts": [acc.model_dump() for acc in settings.accounts.values()]
    }

async def broadcast_status_update():
    """현재 시스템 상태를 모든 웹소켓 클라이언트에게 브로드캐스트합니다."""
    message = json.dumps({"type": "status_update", "payload": get_current_status_payload()})
    await manager.broadcast(message)

def update_dependencies(new_broker: AlpacaBroker):
    """계좌 전환 시 새 브로커 인스턴스로 의존성을 업데이트합니다."""
    runner.broker = new_broker
    terminal_mgr.update_broker(new_broker)

# --- API 엔드포인트 ---
@app.get("/")
async def get_root():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))

@app.get("/health")
async def get_health():
    return {"status": "healthy"}

@app.get("/api/status")
async def get_status():
    return get_current_status_payload()

@app.post("/api/auto")
async def post_auto(req: AutoRequest):
    settings.auto.enabled = req.enabled
    if req.strategy: settings.auto.strategy = req.strategy
    if req.interval_seconds and req.interval_seconds >= 10:
        settings.auto.interval_seconds = req.interval_seconds
    save_settings(settings)

    try:
        job = sched.get_job('auto_trade_job')
        job.reschedule(trigger="interval", seconds=settings.auto.interval_seconds)
        if settings.auto.enabled and settings.auto.strategy:
            job.resume()
            logging.info(f"자동매매 재개. 전략: {settings.auto.strategy}.")
        else:
            job.pause()
            logging.info("자동매매 일시중지.")
    except Exception as e:
        logging.error(f"스케줄러 업데이트 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="스케줄러 제어 실패.")

    await broadcast_status_update()
    return {"ok": True, "auto": settings.auto.model_dump()}

@app.post("/api/account")
async def post_account_switch(req: dict):
    global broker
    account_name = req.get("account")
    if not account_name or account_name not in settings.accounts:
        raise HTTPException(400, "잘못된 계좌 이름입니다.")

    settings.current_account = account_name
    account = settings.accounts[account_name]
    settings.alpaca.update({"key_id": account.key_id, "secret_key": account.secret_key})
    settings.mode = account.type
    save_settings(settings)

    broker = AlpacaBroker(settings)
    update_dependencies(broker)
    
    await broadcast_status_update()
    return {"ok": True, "account": account_name, "mode": settings.mode}

# --- 웹소켓 엔드포인트 ---
@app.websocket("/ws/terminal")
async def ws_terminal(ws: WebSocket):
    await manager.connect(ws)
    await ws.send_text(json.dumps({"type": "terminal_output", "payload": "=== WealthCommander 터미널 v1.0 ===\n도움말: HELP"}))
    await broadcast_status_update()
    
    try:
        while True:
            raw_data = await ws.receive_text()
            if not raw_data.strip(): continue
            line = json.loads(raw_data).get("payload", raw_data) if raw_data.startswith('{') else raw_data
            output = await terminal_mgr.handle_line(line)
            if output:
                await ws.send_text(json.dumps({"type": "terminal_output", "payload": output}))
    except WebSocketDisconnect:
        logging.info("웹소켓 클라이언트 연결 해제.")
    except Exception as e:
        logging.error(f"웹소켓 오류: {e}", exc_info=True)
    finally:
        manager.disconnect(ws)

# --- 정적 파일 마운트 ---
static_dir = os.path.join(BASE_DIR, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    logging.warning(f"정적 파일 디렉토리를 찾을 수 없습니다: {static_dir}")