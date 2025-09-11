# -*- coding: utf-8 -*-
# 한글 주석: 환경 설정 로더

import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

APP_PORT = int(os.getenv("APP_PORT", "8000"))
DATA_FEED = os.getenv("DATA_FEED", "iex")

ALPACA_BASE_URL_LIVE = os.getenv("ALPACA_BASE_URL_LIVE", "https://api.alpaca.markets")
ALPACA_BASE_URL_PAPER = os.getenv("ALPACA_BASE_URL_PAPER", "https://paper-api.alpaca.markets")
ALPACA_DATA_BASE_URL = os.getenv("ALPACA_DATA_BASE_URL", "https://data.alpaca.markets")

DEFAULT_ACCOUNT = os.getenv("DEFAULT_ACCOUNT", "paper1")

# 계정별 API 키
ACCOUNTS = {
    "live": {
        "key": os.getenv("ALPACA_LIVE_KEY_ID", ""),
        "secret": os.getenv("ALPACA_LIVE_SECRET_KEY", ""),
        "base": ALPACA_BASE_URL_LIVE,
        "paper": False,
    },
    "paper1": {
        "key": os.getenv("ALPACA_PAPER1_KEY_ID", ""),
        "secret": os.getenv("ALPACA_PAPER1_SECRET_KEY", ""),
        "base": ALPACA_BASE_URL_PAPER,
        "paper": True,
    },
    "paper2": {
        "key": os.getenv("ALPACA_PAPER2_KEY_ID", ""),
        "secret": os.getenv("ALPACA_PAPER2_SECRET_KEY", ""),
        "base": ALPACA_BASE_URL_PAPER,
        "paper": True,
    },
    "paper3": {
        "key": os.getenv("ALPACA_PAPER3_KEY_ID", ""),
        "secret": os.getenv("ALPACA_PAPER3_SECRET_KEY", ""),
        "base": ALPACA_BASE_URL_PAPER,
        "paper": True,
    },
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
AUTO_METHODS_DIR = os.path.join(DATA_DIR, "auto_methods")
MYETF_DIR = os.path.join(DATA_DIR, "myETF")
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(AUTO_METHODS_DIR, exist_ok=True)
os.makedirs(MYETF_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
