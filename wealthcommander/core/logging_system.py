"""
WealthCommander JSONL Logging System
구조화된 로그 시스템 - 모든 활동 추적
"""

import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import threading

@dataclass
class LogEntry:
    """구조화된 로그 엔트리"""
    timestamp: str
    level: str
    logger: str
    message_key: str
    message: str
    context: Dict[str, Any]
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    account: Optional[str] = None

class JSONLLogger:
    """JSONL 형태의 구조화된 로깅 시스템"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # 로그 파일들
        self.main_log = self.log_dir / "wealthcommander.jsonl"
        self.trading_log = self.log_dir / "trading.jsonl"
        self.system_log = self.log_dir / "system.jsonl"
        self.user_log = self.log_dir / "user_activity.jsonl"
        
        # 스레드 안전성을 위한 락
        self._lock = threading.Lock()
        
        # 메시지 키 매핑
        self.message_keys = {
            # 시스템 메시지
            "system_startup": "시스템 시작",
            "system_shutdown": "시스템 종료",
            "account_init": "계좌 초기화",
            "account_switch": "계좌 전환",
            "config_update": "설정 업데이트",
            
            # 사용자 활동
            "user_command": "사용자 명령 실행",
            "user_login": "사용자 로그인",
            "user_session_start": "사용자 세션 시작",
            "user_session_end": "사용자 세션 종료",
            
            # 거래 활동
            "trade_order_placed": "주문 생성",
            "trade_order_filled": "주문 체결",
            "trade_order_cancelled": "주문 취소",
            "trade_order_failed": "주문 실패",
            "portfolio_update": "포트폴리오 업데이트",
            "quote_request": "시세 조회",
            
            # 자동매매
            "auto_trading_start": "자동매매 시작",
            "auto_trading_stop": "자동매매 중지",
            "strategy_execution": "전략 실행",
            "strategy_signal": "전략 신호",
            
            # API 활동
            "api_request": "API 요청",
            "api_response": "API 응답",
            "api_error": "API 오류",
            "websocket_connect": "웹소켓 연결",
            "websocket_disconnect": "웹소켓 해제",
            
            # 오류 및 경고
            "error_occurred": "오류 발생",
            "warning_issued": "경고 발생",
            "exception_caught": "예외 처리",
        }
    
    def _write_log(self, file_path: Path, entry: LogEntry) -> None:
        """JSONL 파일에 로그 엔트리 작성"""
        with self._lock:
            try:
                with open(file_path, 'a', encoding='utf-8') as f:
                    json.dump(asdict(entry), f, ensure_ascii=False)
                    f.write('\n')
            except Exception as e:
                # 로깅 실패를 콘솔에 출력
                print(f"로그 작성 실패 {file_path}: {e}")
    
    def _create_entry(self, level: str, logger: str, message_key: str, 
                     context: Dict[str, Any], session_id: str = None, 
                     user_id: str = None, account: str = None) -> LogEntry:
        """로그 엔트리 생성"""
        message = self.message_keys.get(message_key, message_key)
        
        return LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level,
            logger=logger,
            message_key=message_key,
            message=message,
            context=context,
            session_id=session_id,
            user_id=user_id,
            account=account
        )
    
    def system(self, message_key: str, **context) -> None:
        """시스템 로그"""
        entry = self._create_entry("INFO", "system", message_key, context)
        self._write_log(self.system_log, entry)
        self._write_log(self.main_log, entry)
    
    def user_activity(self, message_key: str, session_id: str = None, 
                     user_id: str = None, **context) -> None:
        """사용자 활동 로그"""
        entry = self._create_entry("INFO", "user", message_key, context, 
                                 session_id, user_id)
        self._write_log(self.user_log, entry)
        self._write_log(self.main_log, entry)
    
    def trading(self, message_key: str, account: str = None, 
               session_id: str = None, **context) -> None:
        """거래 활동 로그"""
        entry = self._create_entry("INFO", "trading", message_key, context, 
                                 session_id, account=account)
        self._write_log(self.trading_log, entry)
        self._write_log(self.main_log, entry)
    
    def error(self, message_key: str, error: Exception = None, 
             session_id: str = None, **context) -> None:
        """오류 로그"""
        if error:
            context["error_type"] = type(error).__name__
            context["error_message"] = str(error)
        
        entry = self._create_entry("ERROR", "error", message_key, context, session_id)
        self._write_log(self.main_log, entry)
    
    def warning(self, message_key: str, session_id: str = None, **context) -> None:
        """경고 로그"""
        entry = self._create_entry("WARNING", "warning", message_key, context, session_id)
        self._write_log(self.main_log, entry)
    
    def api_activity(self, message_key: str, endpoint: str = None, 
                    method: str = None, status_code: int = None, 
                    session_id: str = None, **context) -> None:
        """API 활동 로그"""
        if endpoint:
            context["endpoint"] = endpoint
        if method:
            context["method"] = method
        if status_code:
            context["status_code"] = status_code
            
        entry = self._create_entry("INFO", "api", message_key, context, session_id)
        self._write_log(self.main_log, entry)
    
    def read_logs(self, log_type: str = "main", limit: int = 100) -> list:
        """로그 파일 읽기"""
        log_files = {
            "main": self.main_log,
            "trading": self.trading_log,
            "system": self.system_log,
            "user": self.user_log
        }
        
        file_path = log_files.get(log_type, self.main_log)
        
        if not file_path.exists():
            return []
        
        logs = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # 최근 로그부터 반환
                for line in lines[-limit:]:
                    if line.strip():
                        logs.append(json.loads(line))
        except Exception as e:
            print(f"로그 읽기 실패 {file_path}: {e}")
        
        return logs
    
    def get_log_summary(self) -> Dict[str, Any]:
        """로그 요약 정보"""
        summary = {
            "files": {},
            "recent_activity": []
        }
        
        # 각 로그 파일 정보
        for name, path in [
            ("main", self.main_log),
            ("trading", self.trading_log), 
            ("system", self.system_log),
            ("user", self.user_log)
        ]:
            if path.exists():
                stat = path.stat()
                summary["files"][name] = {
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "lines": sum(1 for _ in open(path, 'r'))
                }
            else:
                summary["files"][name] = {"size": 0, "lines": 0}
        
        # 최근 활동
        summary["recent_activity"] = self.read_logs("main", 10)
        
        return summary

# 전역 로거 인스턴스
wealth_logger = JSONLLogger()

# 편의 함수들
def log_system(message_key: str, **context):
    """시스템 로그 편의 함수"""
    wealth_logger.system(message_key, **context)

def log_user_activity(message_key: str, session_id: str = None, **context):
    """사용자 활동 로그 편의 함수"""
    wealth_logger.user_activity(message_key, session_id=session_id, **context)

def log_trading(message_key: str, account: str = None, session_id: str = None, **context):
    """거래 활동 로그 편의 함수"""
    wealth_logger.trading(message_key, account=account, session_id=session_id, **context)

def log_error(message_key: str, error: Exception = None, session_id: str = None, **context):
    """오류 로그 편의 함수"""
    wealth_logger.error(message_key, error=error, session_id=session_id, **context)

def log_api(message_key: str, endpoint: str = None, method: str = None, 
           status_code: int = None, session_id: str = None, **context):
    """API 활동 로그 편의 함수"""
    wealth_logger.api_activity(message_key, endpoint=endpoint, method=method, 
                              status_code=status_code, session_id=session_id, **context)