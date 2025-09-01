# app/config.py
import json
import os
from pydantic import BaseModel
from typing import Optional, List, Dict
from dotenv import load_dotenv
import pytz
from datetime import datetime, timedelta

# .env 파일 로드
load_dotenv()

class AutoCfg(BaseModel):
    enabled: bool = False
    interval_seconds: int = 60
    strategy: Optional[str] = None

class AlpacaAccount(BaseModel):
    key_id: Optional[str] = None
    secret_key: Optional[str] = None
    name: str = ""
    type: str = "PAPER"  # LIVE or PAPER

class Settings(BaseModel):
    language: str = "ko"
    date_format: str = "YYYY-MM-DD"
    colors: Dict[str, str] = {"up": "#ef4444", "down": "#0ea5e9"}
    mode: str = "PAPER"
    auto: AutoCfg = AutoCfg()
    allow_fractional: bool = True
    alpaca: Dict[str, Optional[str]] = {"key_id": None, "secret_key": None}
    # 다중 계좌 설정
    accounts: Dict[str, AlpacaAccount] = {}
    current_account: str = "PAPER1"
    timezone: str = "America/New_York"

CFG_PATH = "config/user-defined.json"

def get_market_colors(language: str) -> Dict[str, str]:
    """언어 설정에 따른 색상 반환"""
    if language == "us":
        return {"up": "#10b981", "down": "#ef4444"}
    else:
        return {"up": "#ef4444", "down": "#0ea5e9"}

def load_accounts_from_env() -> Dict[str, AlpacaAccount]:
    """환경 변수에서 계좌 정보 로드"""
    accounts = {}
    
    # Live Account
    live_key = os.getenv("ALPACA_LIVE_KEY_ID")
    live_secret = os.getenv("ALPACA_LIVE_SECRET_KEY")
    if live_key and live_secret:
        accounts["LIVE"] = AlpacaAccount(
            key_id=live_key,
            secret_key=live_secret,
            name="Live Account",
            type="LIVE"
        )
    
    # Paper Accounts
    for i in range(1, 4):
        paper_key = os.getenv(f"ALPACA_PAPER{i}_KEY_ID")
        paper_secret = os.getenv(f"ALPACA_PAPER{i}_SECRET_KEY")
        if paper_key and paper_secret:
            accounts[f"PAPER{i}"] = AlpacaAccount(
                key_id=paper_key,
                secret_key=paper_secret,
                name=f"Paper Account {i}",
                type="PAPER"
            )
    
    return accounts

def load_settings() -> Settings:
    """설정 파일을 로드하고 환경 변수로 덮어씁니다."""
    # 기본 설정
    data = {
        "language": "ko",
        "date_format": "YYYY-MM-DD",
        "mode": "PAPER",
        "auto": {"enabled": False, "interval_seconds": 60, "strategy": None},
        "allow_fractional": True,
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
    
    # 색상 설정
    data["colors"] = get_market_colors(data.get("language", "ko"))
    
    # 다중 계좌 로드
    accounts = load_accounts_from_env()
    data["accounts"] = {k: v.model_dump() for k, v in accounts.items()}
    
    # 기본 계좌 선택
    default_account = os.getenv("DEFAULT_ACCOUNT", "PAPER1")
    if default_account in accounts:
        data["current_account"] = default_account
        account = accounts[default_account]
        data["alpaca"] = {
            "key_id": account.key_id,
            "secret_key": account.secret_key
        }
        data["mode"] = account.type
    
    return Settings(**data)

def save_settings(s: Settings):
    """설정을 파일에 저장합니다."""
    os.makedirs(os.path.dirname(CFG_PATH), exist_ok=True)
    s.colors = get_market_colors(s.language)
    
    # 저장시 계좌 정보는 제외 (보안)
    save_data = json.loads(s.model_dump_json())
    save_data.pop("accounts", None)
    save_data.pop("alpaca", None)
    
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

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
    
    if weekday >= 5:
        return False
    
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
    ny_tz = pytz.timezone('America/New_York')
    ny_time = get_ny_time()
    
    next_day = ny_time + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    
    next_open = next_day.replace(hour=9, minute=30, second=0)
    return next_open.strftime("%Y-%m-%d %H:%M:%S ET")