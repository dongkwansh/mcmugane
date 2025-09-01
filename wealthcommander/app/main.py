# app/main.py
import logging
import json
import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel

from config import load_settings, save_settings, list_strategies, Settings
from logging_setup import setup_logging
from alpaca_client import AlpacaBroker
from strategies.runner import StrategyRunner
from terminal.session import TerminalSessionManager

# 전역 변수
settings: Settings = None
broker: AlpacaBroker = None
runner: StrategyRunner = None
sched: AsyncIOScheduler = None
terminal_mgr: TerminalSessionManager = None

# WebSocket 연결 관리
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
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

def get_current_status_payload():
    """현재 상태 페이로드 생성"""
    from config import get_market_status
    
    return {
        "mode": settings.mode,
        "auto": settings.auto.model_dump(),
        "strategy": settings.auto.strategy,
        "strategies": list_strategies(),
        "alpaca": "OK" if broker.enabled else "NO-CREDS",
        "buying_power": broker.buying_power() if broker.enabled else 0,
        "language": settings.language,
        "colors": settings.colors,
        "market": get_market_status()
    }

async def broadcast_status_update():
    """상태 브로드캐스트"""
    status_payload = get_current_status_payload()
    message = json.dumps({"type": "status_update", "payload": status_payload})
    await manager.broadcast(message)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기"""
    global settings, broker, runner, sched, terminal_mgr
    
    # 시작
    settings = load_settings()
    setup_logging("logs")
    
    broker = AlpacaBroker(settings)
    runner = StrategyRunner(broker, settings)
    
    sched = AsyncIOScheduler({'apscheduler.timezone': 'Asia/Seoul'})
    
    # 자동매매 작업 추가
    sched.add_job(
        runner.tick,
        "interval",
        seconds=settings.auto.interval_seconds,
        id="auto",
        replace_existing=True
    )
    
    if settings.auto.enabled:
        sched.start()
        logging.getLogger("init").info("자동매매 활성화됨")
    
    terminal_mgr = TerminalSessionManager(
        broker, runner, settings, 
        scheduler=sched, 
        on_state_change=broadcast_status_update
    )
    
    logging.getLogger("init").info(
        f"시스템 초기화 완료 (Alpaca: {broker.enabled})"
    )
    
    yield
    
    # 종료
    if sched.running:
        sched.shutdown()
    logging.getLogger("shutdown").info("시스템 종료")

# FastAPI 앱
app = FastAPI(lifespan=lifespan)

# API 모델
class ModeRequest(BaseModel):
    mode: str

class AutoRequest(BaseModel):
    enabled: bool
    strategy: Optional[str] = None
    interval_seconds: Optional[int] = None

# API 엔드포인트
@app.get("/api/status")
async def status():
    """상태 조회 - 시장 상태 포함"""
    from config import get_market_status
    
    base_status = get_current_status_payload()
    market_status = get_market_status()
    
    return {
        **base_status,
        "market": market_status,
        "language": settings.language,
        "colors": settings.colors
    }

@app.post("/api/mode")
async def set_mode(request: ModeRequest):
    """모드 변경"""
    global broker
    
    if request.mode not in ("PAPER", "LIVE"):
        raise HTTPException(400, "잘못된 모드")
    
    settings.mode = request.mode
    save_settings(settings)
    
    # Broker 재초기화
    broker = AlpacaBroker(settings)
    terminal_mgr.update_broker(broker)
    runner.broker = broker
    
    await broadcast_status_update()
    return {"ok": True, "mode": settings.mode}

@app.post("/api/auto")
async def set_auto(request: AutoRequest):
    """자동매매 설정"""
    settings.auto.enabled = request.enabled
    if request.strategy:
        settings.auto.strategy = request.strategy
    if request.interval_seconds:
        settings.auto.interval_seconds = request.interval_seconds
    
    save_settings(settings)
    
    # 스케줄러 업데이트
    try:
        if sched.get_job("auto"):
            sched.reschedule_job(
                "auto",
                trigger="interval",
                seconds=settings.auto.interval_seconds
            )
        
        if request.enabled:
            if not sched.running:
                sched.start()
        else:
            if sched.running:
                sched.pause()
    except Exception as e:
        logging.getLogger("api").error(f"스케줄러 오류: {e}")
    
    await broadcast_status_update()
    return {"ok": True, "auto": settings.auto.model_dump()}
@app.post("/api/settings/language")
async def set_language(request: dict):
    """언어 설정 변경"""
    language = request.get("language", "ko")
    if language not in ["ko", "us"]:
        raise HTTPException(400, "Invalid language")
    
    settings.language = language
    settings.colors = get_market_colors(language)
    save_settings(settings)
    
    await broadcast_status_update()
    return {"ok": True, "language": language, "colors": settings.colors}
@app.websocket("/ws/terminal")
async def ws_terminal(ws: WebSocket):
    """터미널 WebSocket"""
    await manager.connect(ws)
    
    # 환영 메시지
    await ws.send_text(json.dumps({
        "type": "terminal_output",
        "payload": "=== MCMUGANE 터미널 v1.0 ===\n도움말: HELP"
    }))
    
    try:
        while True:
            raw_data = await ws.receive_text()
            
            try:
                data = json.loads(raw_data)
                
                if data.get("type") == "terminal_input":
                    line = data.get("payload", "")
                    output = await terminal_mgr.handle_line(line)
                    
                    await ws.send_text(json.dumps({
                        "type": "terminal_output",
                        "payload": output
                    }))
            except json.JSONDecodeError:
                # 일반 텍스트로 처리
                output = await terminal_mgr.handle_line(raw_data)
                await ws.send_text(json.dumps({
                    "type": "terminal_output",
                    "payload": output
                }))
                
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        logging.getLogger("ws").error(f"WebSocket 오류: {e}")
        manager.disconnect(ws)

# 정적 파일
app.mount("/", StaticFiles(directory="static", html=True), name="static")