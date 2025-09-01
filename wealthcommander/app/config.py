# app/config.py
import json
import os
from pydantic import BaseModel, Field
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
    auto: AutoCfg = Field(default_factory=AutoCfg)
    allow_fractional: bool = True
    alpaca: Dict[str, Optional[str]] = {"key_id": None, "secret_key": None}
    accounts: Dict[str, AlpacaAccount] = Field(default_factory=dict)
    current_account: str = "PAPER1"
    timezone: str = "America/New_York"

CFG_PATH = "config/user-defined.json"

def get_market_colors(language: str) -> Dict[str, str]:
    """언어 설정에 따른 색상 반환"""
    if language == "us":
        return {"up": "#10b981", "down": "#ef4444"}
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
    base_data = {
        "language": "ko",
        "date_format": "YYYY-MM-DD",
        "mode": "PAPER",
        "auto": {"enabled": False, "interval_seconds": 60, "strategy": None},
        "allow_fractional": True,
        "timezone": "America/New_York"
    }

    if os.path.exists(CFG_PATH):
        try:
            with open(CFG_PATH, "r", encoding="utf-8") as f:
                file_data = json.load(f)
                base_data.update(file_data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"설정 파일({CFG_PATH}) 로드 오류: {e}. 기본 설정으로 시작합니다.")

    settings = Settings(**base_data)
    settings.colors = get_market_colors(settings.language)
    settings.accounts = load_accounts_from_env()

    default_account = os.getenv("DEFAULT_ACCOUNT", "PAPER1")
    if settings.current_account not in settings.accounts:
         settings.current_account = default_account if default_account in settings.accounts else next(iter(settings.accounts), None)

    if settings.current_account:
        account = settings.accounts[settings.current_account]
        settings.alpaca["key_id"] = account.key_id
        settings.alpaca["secret_key"] = account.secret_key
        settings.mode = account.type

    return settings

def save_settings(s: Settings):
    """설정을 파일에 저장합니다."""
    os.makedirs(os.path.dirname(CFG_PATH), exist_ok=True)
    s.colors = get_market_colors(s.language)

    # 저장 시 보안상 민감한 정보 제외
    save_data = s.model_dump(exclude={'accounts', 'alpaca'})

    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

def list_strategies() -> List[str]:
    """전략 목록을 가져옵니다."""
    path = "config/strategies"
    if not os.path.exists(path) or not os.path.isdir(path):
        return []
    return sorted([p[:-5] for p in os.listdir(path) if p.endswith(".json")])

def get_ny_time() -> datetime:
    """뉴욕 시간 반환"""
    ny_tz = pytz.timezone('America/New_York')
    return datetime.now(ny_tz)

def is_market_open(now: datetime = None) -> bool:
    """미국 주식시장 개장 여부 확인"""
    ny_time = now or get_ny_time()
    
    # 주말 확인
    if ny_time.weekday() >= 5:
        return False
    
    # TODO: 미국 공휴일 확인 로직 추가 (필요시)
    
    market_open = ny_time.replace(hour=9, minute=30, second=0, microsecond=0).time()
    market_close = ny_time.replace(hour=16, minute=0, second=0, microsecond=0).time()
    
    return market_open <= ny_time.time() <= market_close

def get_next_market_open(now: datetime = None) -> str:
    """다음 개장 시간 반환"""
    ny_time = now or get_ny_time()
    
    # 현재 시간이 개장 전이면 오늘 개장 시간 반환
    if ny_time.time() < ny_time.replace(hour=9, minute=30, second=0).time():
        next_open_day = ny_time
    else:
        next_open_day = ny_time + timedelta(days=1)

    # 다음 영업일 찾기
    while next_open_day.weekday() >= 5: # 토, 일요일 건너뛰기
        next_open_day += timedelta(days=1)
    
    # TODO: 공휴일이면 하루 더하기
    
    next_open_time = next_open_day.replace(hour=9, minute=30, second=0, microsecond=0)
    return next_open_time.strftime("%Y-%m-%d %H:%M:%S ET")


def get_market_status() -> Dict[str, any]:
    """시장 상태 정보 반환"""
    ny_time = get_ny_time()
    is_open = is_market_open(ny_time)
    
    return {
        "is_open": is_open,
        "ny_time": ny_time.strftime("%Y-%m-%d %H:%M:%S ET"),
        "status": "OPEN" if is_open else "CLOSED",
        "next_open": get_next_market_open(ny_time) if not is_open else None
    }