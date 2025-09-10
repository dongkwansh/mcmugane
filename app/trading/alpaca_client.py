# -*- coding: utf-8 -*-
# 한글 주석: Alpaca REST API 간단 래퍼 (주문/계좌/시세)
import requests, time, math, datetime
from typing import Dict, Any, List, Optional, Tuple

from ..config import ALPACA_BASE_URL_LIVE, ALPACA_BASE_URL_PAPER, ALPACA_DATA_BASE_URL, DATA_FEED

ET = datetime.timezone(datetime.timedelta(hours=-5))  # 고정값(서머타임 보정은 간단화). UI에서 표시만 사용.

def _headers(key: str, secret: str) -> Dict[str, str]:
    return {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
        "Content-Type": "application/json",
    }

class AlpacaClient:
    """Alpaca 트레이딩/데이터 통합 클라이언트 (requests 기반)"""
    def __init__(self, key: str, secret: str, paper: bool = True):
        self.key = key
        self.secret = secret
        self.paper = paper
        self.base_trading = ALPACA_BASE_URL_PAPER if paper else ALPACA_BASE_URL_LIVE
        self.base_data = ALPACA_DATA_BASE_URL

    # ---------- 계정/시장 ----------
    def get_account(self) -> Dict[str, Any]:
        url = f"{self.base_trading}/v2/account"
        r = requests.get(url, headers=_headers(self.key, self.secret), timeout=15)
        r.raise_for_status()
        return r.json()

    def get_clock(self) -> Dict[str, Any]:
        # 시장 상태(단순 버전)
        url = f"{self.base_trading}/v2/clock"
        r = requests.get(url, headers=_headers(self.key, self.secret), timeout=15)
        r.raise_for_status()
        return r.json()

    # ---------- 시세/바 ----------
    def get_latest_trade(self, symbol: str) -> Optional[float]:
        # 최신 체결가
        url = f"{self.base_data}/v2/stocks/{symbol}/trades/latest?feed={DATA_FEED}"
        r = requests.get(url, headers=_headers(self.key, self.secret), timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        try:
            return float(data.get("trade", {}).get("p"))
        except Exception:
            return None

    def get_daily_ohlc(self, symbol: str, limit: int = 2) -> Optional[List[Dict[str, Any]]]:
        # 일봉(최근 N개) 가져오기
        url = f"{self.base_data}/v2/stocks/{symbol}/bars?timeframe=1Day&limit={limit}&feed={DATA_FEED}"
        r = requests.get(url, headers=_headers(self.key, self.secret), timeout=20)
        if r.status_code != 200:
            return None
        return r.json().get("bars", [])

    def get_bars(self, symbol: str, timeframe: str = "15Min", limit: int = 100) -> Optional[List[Dict[str, Any]]]:
        # intraday / multi
        url = f"{self.base_data}/v2/stocks/{symbol}/bars?timeframe={timeframe}&limit={limit}&feed={DATA_FEED}"
        r = requests.get(url, headers=_headers(self.key, self.secret), timeout=20)
        if r.status_code != 200:
            return None
        return r.json().get("bars", [])

    # ---------- 주문/포지션 ----------
    def list_positions(self) -> List[Dict[str, Any]]:
        url = f"{self.base_trading}/v2/positions"
        r = requests.get(url, headers=_headers(self.key, self.secret), timeout=15)
        r.raise_for_status()
        return r.json()

    def list_orders(self, status: str = "open", limit: int = 50) -> List[Dict[str, Any]]:
        url = f"{self.base_trading}/v2/orders?status={status}&limit={limit}&nested=true"
        r = requests.get(url, headers=_headers(self.key, self.secret), timeout=15)
        r.raise_for_status()
        return r.json()

    def cancel_order(self, order_id: str) -> bool:
        url = f"{self.base_trading}/v2/orders/{order_id}"
        r = requests.delete(url, headers=_headers(self.key, self.secret), timeout=15)
        return r.status_code in (200, 204)

    def submit_order(self,
                     symbol: str,
                     side: str,
                     qty: Optional[float] = None,
                     notional: Optional[float] = None,
                     type_: str = "limit",
                     time_in_force: str = "day",
                     limit_price: Optional[float] = None,
                     extended_hours: bool = False) -> Dict[str, Any]:
        # qty 또는 notional 중 하나 사용 (limit 주문의 경우 qty 필요)
        payload = {
            "symbol": symbol,
            "side": side,
            "type": type_,
            "time_in_force": time_in_force,
            "extended_hours": extended_hours,
        }
        if limit_price is not None:
            payload["limit_price"] = round(float(limit_price), 4)
        if qty is not None:
            # 소수점 4자리까지 허용 (Alpaca fractional 최소 0.0001)
            payload["qty"] = float(f"{float(qty):.4f}")
        elif notional is not None:
            payload["notional"] = round(float(notional), 2)

        url = f"{self.base_trading}/v2/orders"
        r = requests.post(url, json=payload, headers=_headers(self.key, self.secret), timeout=20)
        if r.status_code not in (200, 201):
            # 에러 메시지 전달
            try:
                return {"error": r.json()}
            except Exception:
                return {"error": {"message": r.text, "status": r.status_code}}
        return r.json()

    def get_activities(self, activity_types: str = "FILL", page_size: int = 50) -> List[Dict[str, Any]]:
        # 체결 등 히스토리
        url = f"{self.base_trading}/v2/account/activities?activity_types={activity_types}&page_size={page_size}"
        r = requests.get(url, headers=_headers(self.key, self.secret), timeout=15)
        r.raise_for_status()
        return r.json()
