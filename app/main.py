import logging
import json
import asyncio
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- 내부 모듈 임포트 ---
from config import load_settings, save_settings, list_strategies, Settings
from logging_setup import setup_logging
from alpaca_client import AlpacaBroker
from strategies.runner import StrategyRunner
from terminal.session import TerminalSessionManager

# --- 전역 변수 및 객체 관리 ---
# 애플리케이션의 상태를 관리하는 변수들
# lifespan 내에서 초기화됨
settings: Settings
broker: AlpacaBroker
runner: StrategyRunner
sched: AsyncIOScheduler
terminal_mgr: TerminalSessionManager
# 활성화된 WebSocket 클라이언트 목록을 관리하는 ConnectionManager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    # 모든 클라이언트에게 메시지를 브로드캐스트하는 함수
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# --- 상태 관리 및 브로드캐스팅 ---
def get_current_status_payload():
    """UI 업데이트를 위한 현재 애플리케이션 상태 페이로드를 생성합니다."""
    return {
        "mode": settings.mode,
        "auto": settings.auto.model_dump(), # pydantic 모델을 dict로 변환
        "strategy": settings.auto.strategy,
        "strategies": list_strategies(),
        "alpaca": "OK" if broker.enabled else "NO-CREDS"
    }

async def broadcast_status_update():
    """모든 연결된 클라이언트에게 현재 상태를 브로드캐스트합니다."""
    status_payload = get_current_status_payload()
    message = json.dumps({"type": "status_update", "payload": status_payload})
    await manager.broadcast(message)

# --- 애플리케이션 생명주기 관리 (시작/종료) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- 애플리케이션 시작 시 실행될 코드 ---
    global settings, broker, runner, sched, terminal_mgr
    
    settings = load_settings()
    setup_logging("logs")
    
    broker = AlpacaBroker(settings)
    runner = StrategyRunner(broker, settings)
    
    sched = AsyncIOScheduler({'apscheduler.timezone': 'Asia/Seoul'})
    sched.add_job(
        runner.tick, 
        "interval", 
        seconds=settings.auto.interval_seconds, 
        id="auto", 
        replace_existing=True
    )
    
    if settings.auto.enabled:
        sched.start()
        logging.getLogger("init").info("자동매매 활성화 상태로 스케줄러를 시작합니다.")
        
    # 터미널 관리자 초기화 시 broadcast 함수를 콜백으로 전달
    terminal_mgr = TerminalSessionManager(broker, runner, settings, scheduler=sched, on_state_change=broadcast_status_update)
    
    logging.getLogger("init").info(json.dumps({
        "event": "boot", "alpaca_credentials": broker.enabled
    }))
    
    yield # --- FastAPI 애플리케이션 실행 ---
    
    # --- 애플리케이션 종료 시 실행될 코드 ---
    if sched.running:
        sched.shutdown()
    logging.getLogger("shutdown").info("애플리케이션을 종료합니다.")

# --- FastAPI 앱 초기화 ---
app = FastAPI(lifespan=lifespan)

# --- API 엔드포인트 ---
@app.get("/api/status")
async def status():
    """웹 UI의 초기 상태 로드를 위한 엔드포인트."""
    return get_current_status_payload()

@app.post("/api/mode")
async def set_mode(mode: str):
    """거래 모드(PAPER/LIVE)를 변경합니다."""
    global broker # 전역 broker 객체를 수정함을 명시
    if mode not in ("PAPER", "LIVE"):
        raise HTTPException(400, "잘못된 모드입니다. 'PAPER' 또는 'LIVE'를 사용하세요.")
    
    settings.mode = mode
    save_settings(settings)
    
    # 중요: 모드가 변경되었으므로, 새 모설정에 맞춰 AlpacaBroker를 다시 초기화합니다.
    # 이것이 '.env' 파일의 키가 올바르게 적용되게 하는 핵심입니다.
    broker = AlpacaBroker(settings)
    terminal_mgr.update_broker(broker) # 터미널 관리자에게도 변경된 broker 객체를 알려줍니다.
    
    await broadcast_status_update() # 상태 변경을 모든 클라이언트에 알립니다.
    return {"ok": True, "mode": settings.mode}

@app.post("/api/auto")
async def set_auto(enabled: bool, strategy: str = None, interval_seconds: int = None):
    """자동매매 설정을 변경합니다."""
    settings.auto.enabled = enabled
    if strategy: settings.auto.strategy = strategy
    if interval_seconds: settings.auto.interval_seconds = interval_seconds
    
    save_settings(settings)

    try:
        # 스케줄러 작업 업데이트
        if sched.get_job("auto"):
            sched.reschedule_job("auto", trigger="interval", seconds=settings.auto.interval_seconds)
        else:
            sched.add_job(runner.tick, "interval", seconds=settings.auto.interval_seconds, id="auto")

        # 스케줄러 상태 변경 (시작/일시정지/재개)
        if enabled:
            if not sched.running: sched.start()
            elif sched.paused: sched.resume()
        elif sched.running and not sched.paused:
            sched.pause()
            
    except Exception as e:
        logging.getLogger("api").error(f"스케줄러 업데이트 실패: {e}", exc_info=True)
        raise HTTPException(500, "스케줄러 업데이트에 실패했습니다.")

    await broadcast_status_update() # 상태 변경을 모든 클라이언트에 알립니다.
    return {"ok": True, "auto": settings.auto.model_dump()}

# --- WebSocket 엔드포인트 ---
@app.websocket("/ws/terminal")
async def ws_terminal(ws: WebSocket):
    """터미널 입출력을 위한 WebSocket 통신을 처리합니다."""
    await manager.connect(ws)
    # 초기 접속 메시지 전송
    await ws.send_text(json.dumps({"type": "terminal_output", "payload": "mcmugane 터미널. 도움말은 HELP를 입력하세요."}))
    try:
        while True:
            # 클라이언트로부터 메시지(JSON 형식) 수신
            raw_data = await ws.receive_text()
            data = json.loads(raw_data)

            # 터미널 명령어 처리
            if data.get("type") == "terminal_input":
                line = data.get("payload", "")
                out = await terminal_mgr.handle_line(line)
                # 명령어 결과를 해당 클라이언트에게만 전송
                await ws.send_text(json.dumps({"type": "terminal_output", "payload": out}))

    except WebSocketDisconnect:
        manager.disconnect(ws)
        logging.getLogger("ws").info("WebSocket 클라이언트 연결이 끊어졌습니다.")
    except Exception as e:
        logging.getLogger("ws").error(f"WebSocket 오류 발생: {e}", exc_info=True)
        manager.disconnect(ws)

# --- 정적 파일 마운트 ---
# 다른 모든 라우트 설정 뒤에 위치해야 합니다.
app.mount("/", StaticFiles(directory="static", html=True), name="static")