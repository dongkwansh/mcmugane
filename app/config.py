# app/config.py
import json
import os
from pydantic import BaseModel
from typing import Optional, List, Dict

# --- Pydantic 모델 정의 ---
# 자동매매 설정을 위한 모델
class AutoCfg(BaseModel):
    enabled: bool = False
    interval_seconds: int = 60
    strategy: Optional[str] = None

# 전체 사용자 설정을 위한 모델
class Settings(BaseModel):
    language: str = "ko"
    date_format: str = "YYYY-MM-DD"
    colors: Dict[str, str] = {"up":"#d91c1c","down":"#1763cf"}
    mode: str = "PAPER"     # PAPER | LIVE
    auto: AutoCfg = AutoCfg()
    allow_fractional: bool = True
    alpaca: Dict[str, Optional[str]] = {"key_id": None, "secret_key": None}

# --- 설정 파일 경로 ---
CFG_PATH = "config/user-defined.json"

# --- 함수 정의 ---
def load_settings() -> Settings:
    """user-defined.json 파일에서 설정을 로드하고 환경 변수로 덮어씁니다."""
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # .env 파일에 설정된 환경변수가 우선순위를 가집니다.
    env_key = os.getenv("ALPACA_API_KEY_ID")
    env_sec = os.getenv("ALPACA_API_SECRET_KEY")
    if env_key and env_sec:
        data.setdefault("alpaca", {})
        data["alpaca"]["key_id"] = env_key
        data["alpaca"]["secret_key"] = env_sec
        
    return Settings(**data)

def save_settings(s: Settings):
    """설정 객체를 user-defined.json 파일에 저장합니다."""
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        # Pydantic 모델을 JSON으로 변환하여 저장
        json.dump(json.loads(s.model_dump_json()), f, ensure_ascii=False, indent=2)

def list_strategies() -> List[str]:
    """config/strategies 디렉토리에서 사용 가능한 전략 목록을 가져옵니다."""
    path = "config/strategies"
    if not os.path.exists(path):
        return []
    # .json 확장자를 제외한 파일 이름만 리스트로 반환
    return [p[:-5] for p in os.listdir(path) if p.endswith(".json")]