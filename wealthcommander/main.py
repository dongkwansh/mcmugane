#!/usr/bin/env python3
"""
WealthCommander Trading System - Optimized for Synology NAS 923+
FastAPI-based automated trading system with enhanced performance
"""

import asyncio
import logging
from contextlib import asynccontextmanager
import os
import sys
from typing import Dict, Any, Optional

# FastAPI and web dependencies
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# APScheduler for automated trading
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

# Import optimized modules
from core.alpaca_client import AlpacaBroker
from core.config_manager import ConfigManager
from core.strategy_runner import StrategyRunner
from core.terminal_handler import TerminalHandler
from core.websocket_manager import WebSocketManager
from core.logging_system import log_system, log_api, log_error, wealth_logger

# Set up optimized logging for Container environment
def setup_container_logging():
    """Container-optimized logging setup with detailed activity tracking"""
    from logging.handlers import RotatingFileHandler
    
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create rotating file handler for main log
    main_handler = RotatingFileHandler(
        'logs/wealthcommander.log', 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    main_handler.setLevel(logging.INFO)
    main_handler.setFormatter(logging.Formatter(log_format))
    
    # Create separate handler for trading activities
    trading_handler = RotatingFileHandler(
        'logs/trading.log',
        maxBytes=5*1024*1024,   # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    trading_handler.setLevel(logging.INFO)
    trading_handler.setFormatter(logging.Formatter(log_format))
    
    # Console handler for container output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    root_logger.addHandler(main_handler)
    root_logger.addHandler(console_handler)
    
    # Configure trading logger
    trading_logger = logging.getLogger('trading')
    trading_logger.addHandler(trading_handler)
    trading_logger.setLevel(logging.INFO)
    
    # Reduce noise from external libraries
    logging.getLogger('alpaca').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('websockets').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)

# Application lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown handling"""
    logger = logging.getLogger("startup")
    
    try:
        # Initialize configuration first
        config_manager = ConfigManager()
        
        # Initialize core components and JSONL logging
        logger.info("WealthCommander 시스템 시작")
        log_system("system_startup", version="2.0", environment="container")
        
        app.state.config = config_manager
        
        # Initialize Alpaca broker
        broker = AlpacaBroker(config_manager)
        await broker.initialize()
        app.state.broker = broker
        
        # Initialize WebSocket manager
        ws_manager = WebSocketManager()
        app.state.ws_manager = ws_manager
        
        # Initialize strategy runner with scheduler
        jobstores = {'default': MemoryJobStore()}
        executors = {'default': AsyncIOExecutor()}
        job_defaults = {'coalesce': False, 'max_instances': 3}
        
        scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='America/New_York'
        )
        
        strategy_runner = StrategyRunner(broker, config_manager, ws_manager, scheduler)
        app.state.strategy_runner = strategy_runner
        app.state.scheduler = scheduler
        
        # Initialize terminal handler
        terminal_handler = TerminalHandler(broker, strategy_runner, ws_manager, scheduler)
        app.state.terminal_handler = terminal_handler
        
        # Start scheduler
        scheduler.start()
        logger.info(config_manager.get_message('scheduler_started'))
        
        # Start automated trading if enabled
        if config_manager.get_auto_trading_config().get('enabled', False):
            await strategy_runner.start_auto_trading()
            logger.info(config_manager.get_message('auto_trading_init'))
        
        # Apply container optimizations
        await configure_for_container()
        
        logger.info(config_manager.get_message('init_complete'))
        
        yield
        
    except Exception as e:
        if 'config_manager' in locals():
            logger.error(config_manager.get_message('init_failed', error=str(e)))
        else:
            logger.error(f"❌ 초기화 실패: {e}")
        raise
    finally:
        # Cleanup
        if 'config_manager' in locals():
            logger.info(config_manager.get_message('app_shutdown'))
        else:
            logger.info("🛑 WealthCommander 종료 중...")
        if hasattr(app.state, 'scheduler'):
            app.state.scheduler.shutdown(wait=False)
        if 'config_manager' in locals():
            logger.info(config_manager.get_message('shutdown_complete'))
        else:
            logger.info("✅ 정상 종료됨")

# Create FastAPI application
app = FastAPI(
    title="WealthCommander Trading System",
    description="Automated Stock Trading System for Synology NAS",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware for NAS environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # NAS 환경에서 접근 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# API Routes
@app.get("/")
async def serve_app():
    """Serve main application"""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load application: {e}")

@app.get("/api/status")
async def get_status():
    """Get system status"""
    try:
        broker = app.state.broker
        config = app.state.config
        strategy_runner = app.state.strategy_runner
        
        # Get market status
        market_status = await broker.get_market_status()
        
        # Get account information
        account_info = await broker.get_account_info()
        
        # Get auto trading status
        auto_status = strategy_runner.get_status()
        
        return JSONResponse({
            "status": "running",
            "market": market_status,
            "account": account_info,
            "auto": auto_status,
            "current_account": config.get_current_account(),
            "default_account": config.get_default_account(),
            "timestamp": broker.get_market_time().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Status query failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/accounts")
async def get_accounts():
    """Get available accounts"""
    try:
        config = app.state.config
        accounts = config.get_available_accounts()
        current = config.get_current_account()
        
        return JSONResponse({
            "accounts": accounts,
            "current_account": current,
            "default_account": config.get_default_account()
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/strategies")
async def get_strategies():
    """Get available strategies"""
    try:
        config = app.state.config
        strategies = config.get_strategies_config()
        
        return JSONResponse(strategies)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/terminal")
async def terminal_command(request: Dict[str, str]):
    """Process terminal command via REST API"""
    try:
        command = request.get("command", "")
        client_id = request.get("client_id")
        
        # 빈 명령어도 허용 (시장가 주문을 위한 엔터키)
        result = await app.state.terminal_handler.process_command(command, client_id)
        return JSONResponse({"result": result})
        
    except Exception as e:
        logging.error(f"Terminal API error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/account")
async def switch_account(request: Dict[str, str]):
    """Switch trading account"""
    try:
        account_name = request.get("account")
        if not account_name:
            raise ValueError("Account name required")
            
        config = app.state.config
        config.switch_account(account_name)
        
        # Reinitialize broker with new account
        broker = AlpacaBroker(config)
        await broker.initialize()
        app.state.broker = broker
        
        # Update terminal handler
        app.state.terminal_handler.update_broker(broker)
        
        return JSONResponse({"message": f"Switched to {account_name}"})
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# WebSocket endpoint for terminal
@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    """Terminal WebSocket handler"""
    await websocket.accept()
    client_id = id(websocket)
    
    try:
        # Register client
        await app.state.ws_manager.add_client(client_id, websocket)
        
        # Send welcome message
        await app.state.ws_manager.send_to_client(client_id, {
            "type": "terminal_output",
            "payload": "🚀 WealthCommander 터미널에 연결되었습니다.\n명령어 도움말을 보려면 'HELP'를 입력하세요."
        })
        
        # Handle messages
        while True:
            try:
                data = await websocket.receive_text()
                if data:
                    # Process terminal command
                    result = await app.state.terminal_handler.process_command(data.strip(), client_id)
                    if result:
                        await app.state.ws_manager.send_to_client(client_id, {
                            "type": "terminal_output", 
                            "payload": result
                        })
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                logging.error(f"WebSocket error: {e}")
                await app.state.ws_manager.send_to_client(client_id, {
                    "type": "terminal_output",
                    "payload": f"❌ 오류: {e}"
                })
                
    except Exception as e:
        logging.error(f"WebSocket connection error: {e}")
    finally:
        await app.state.ws_manager.remove_client(client_id)

# Health check for container monitoring
@app.get("/health")
async def health_check():
    """Container health check endpoint"""
    try:
        # Quick broker connectivity test
        if hasattr(app.state, 'broker'):
            await app.state.broker.get_account_info()
        
        return JSONResponse({
            "status": "healthy",
            "timestamp": str(asyncio.get_event_loop().time())
        })
    except Exception as e:
        return JSONResponse({
            "status": "unhealthy", 
            "error": str(e)
        }, status_code=503)

# Container optimization - moved to lifespan
async def configure_for_container():
    """Additional container-specific configurations"""
    try:
        # Set optimal asyncio policy for container
        if sys.platform.startswith('linux'):
            try:
                import uvloop
                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
                logging.info("🔧 uvloop 적용됨")
            except ImportError:
                logging.info("🔧 uvloop 없음, 기본 이벤트 루프 사용")
        
        # Configure for NAS resource constraints
        logging.info("🐳 Container 환경 최적화 적용됨")
    except Exception as e:
        logging.warning(f"Container 최적화 실패: {e}")

if __name__ == "__main__":
    setup_container_logging()
    
    # Production-ready server configuration for NAS
    import uvicorn
    
    # Corrected 'main:app' to match the filename and app instance
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        workers=1,
        access_log=False,  # Consistent with Dockerfile CMD
        timeout_keep_alive=30,
        timeout_graceful_shutdown=30
    )