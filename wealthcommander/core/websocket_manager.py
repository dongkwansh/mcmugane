"""
WebSocket Manager - Optimized for Container Environment
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional
from fastapi import WebSocket
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)

class WebSocketManager:
    """WebSocket 연결 관리자 - 컨테이너 최적화"""
    
    def __init__(self):
        self.clients: Dict[int, WebSocket] = {}
        self._lock = asyncio.Lock()
        self.config_manager = ConfigManager()
    
    async def add_client(self, client_id: int, websocket: WebSocket):
        """클라이언트 추가"""
        async with self._lock:
            self.clients[client_id] = websocket
            logger.info(self.config_manager.get_message('websocket_client_connected', client_id=client_id, count=len(self.clients)))
    
    async def remove_client(self, client_id: int):
        """클라이언트 제거"""
        async with self._lock:
            if client_id in self.clients:
                del self.clients[client_id]
                logger.info(self.config_manager.get_message('websocket_client_disconnected', client_id=client_id, count=len(self.clients)))
    
    async def send_to_client(self, client_id: int, message: Dict[str, Any]):
        """특정 클라이언트에게 메시지 전송"""
        try:
            if client_id in self.clients:
                websocket = self.clients[client_id]
                await websocket.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.error(self.config_manager.get_message('websocket_send_failed', client_id=client_id, error=str(e)))
            await self.remove_client(client_id)
    
    async def broadcast(self, message: Dict[str, Any]):
        """모든 클라이언트에게 브로드캐스트"""
        if not self.clients:
            return
        
        disconnected_clients = []
        message_text = json.dumps(message, ensure_ascii=False)
        
        async with self._lock:
            for client_id, websocket in self.clients.items():
                try:
                    await websocket.send_text(message_text)
                except Exception as e:
                    logger.error(self.config_manager.get_message('websocket_broadcast_failed', client_id=client_id, error=str(e)))
                    disconnected_clients.append(client_id)
        
        # 연결이 끊어진 클라이언트 제거
        for client_id in disconnected_clients:
            await self.remove_client(client_id)
    
    def get_client_count(self) -> int:
        """연결된 클라이언트 수"""
        return len(self.clients)