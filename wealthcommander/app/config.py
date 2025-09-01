# app/config.py
import json
import os
from pydantic import BaseModel
from typing import Optional, List, Dict
from dotenv import load_dotenv
import pytz
from datetime import datetime

# .env 파일 로드
load_dotenv()

class AutoCfg(BaseModel):
    enabled: bool = False
    interval_seconds: int = 60
    strategy: Optional[str] = None

class Settings(BaseModel):
    language: str = "ko"  # ko(한국) 또는 us(미국)
    date_format: str = "YYYY-MM-DD"
    colors: Dict[str, str] = {"up": "#d91c1c", "down": "#1763cf"}  # 한국 기본값
    mode: str = "PAPER"
    auto: AutoCfg = AutoCfg()
    allow_fractional: bool = True
    alpaca: Dict[str, Optional[str]] = {"key_id": None, "secret_key": None}
    timezone: str = "America/New_York"  # 뉴욕 시장 기준

CFG_PATH = "config/user-defined.json"

def get_market_colors(language: str) -> Dict[str, str]:
    """언어 설정에 따른 색상 반환"""
    if language == "us":
        # 미국: 상승=녹색, 하락=빨강
        return {"up": "#10b981", "down": "#ef4444"}
    else:
        # 한국: 상승=빨강, 하락=파랑
        return {"up": "#ef4444", "down": "#0ea5e9"}

def load_settings() -> Settings:
    """설정 파일을 로드하고 환경 변수로 덮어씁니다."""
    # 기본 설정
    data = {
        "language": "ko",
        "date_format": "YYYY-MM-DD",
        "mode": "PAPER",
        "auto": {"enabled": False, "interval_seconds": 60, "strategy": None},
        "allow_fractional": True,
        "alpaca": {"key_id": None, "secret_key": None},
        "timezone": "America/New_York"
    }
    
    # 파일이 있으면 로드
    if os.path.exists(CFG_PATH):
        try:
            with open(CFG_PATH, "r", encoding="utf-8") as f:
                file_data = json.load(f)
                data.update(file_data)
        except Exception as e:
            print(f"설정 파일 로드 오류: {e}")
    
    # 언어에 따른 색상 자동 설정
    data["colors"] = get_market_colors(data.get("language", "ko"))
    
    # 환경 변수 우선
    env_key = os.getenv("ALPACA_API_KEY_ID")
    env_sec = os.getenv("ALPACA_API_SECRET_KEY")
    if env_key and env_sec:
        data.setdefault("alpaca", {})
        data["alpaca"]["key_id"] = env_key
        data["alpaca"]["secret_key"] = env_sec
    
    return Settings(**data)

def save_settings(s: Settings):
    """설정을 파일에 저장합니다."""
    os.makedirs(os.path.dirname(CFG_PATH), exist_ok=True)
    # 언어 변경시 색상도 자동 업데이트
    s.colors = get_market_colors(s.language)
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(json.loads(s.model_dump_json()), f, ensure_ascii=False, indent=2)

def list_strategies() -> List[str]:
    """전략 목록을 가져옵니다."""
    path = "config/strategies"
    if not os.path.exists(path):
        return []
    return [p[:-5] for p in os.listdir(path) if p.endswith(".json")]

def get_ny_time() -> datetime:
    """뉴욕 시간 반환"""
    ny_tz = pytz.timezone('America/New_York')
    return datetime.now(ny_tz)

def is_market_open() -> bool:
    """미국 주식시장 개장 여부 확인"""
    ny_time = get_ny_time()
    weekday = ny_time.weekday()
    
    # 주말 제외
    if weekday >= 5:  # 토요일(5), 일요일(6)
        return False
    
    # 시간 확인 (9:30 AM - 4:00 PM ET)
    current_time = ny_time.time()
    market_open = ny_time.replace(hour=9, minute=30, second=0).time()
    market_close = ny_time.replace(hour=16, minute=0, second=0).time()
    
    return market_open <= current_time <= market_close

def get_market_status() -> Dict[str, any]:
    """시장 상태 정보 반환"""
    ny_time = get_ny_time()
    is_open = is_market_open()
    
    return {
        "is_open": is_open,
        "ny_time": ny_time.strftime("%Y-%m-%d %H:%M:%S ET"),
        "status": "OPEN" if is_open else "CLOSED",
        "next_open": get_next_market_open() if not is_open else None
    }

def get_next_market_open() -> str:
    """다음 개장 시간 반환"""
    ny_time = get_ny_time()
    
    # 다음 평일 찾기
    days_ahead = 1
    next_day = ny_time
    
    while True:
        next_day = next_day.replace(hour=9, minute=30, second=0)
        next_day += pytz.timezone('America/New_York').localize(
            datetime.timedelta(days=days_ahead)
        )
        if next_day.weekday() < 5:  # 평일
            return next_day.strftime("%Y-%m-%d %H:%M:%S ET")
        days_ahead += 1