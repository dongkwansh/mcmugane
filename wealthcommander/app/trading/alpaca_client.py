# -*- coding: utf-8 -*-
# 한글 주석: Alpaca REST API 간단 래퍼 (주문/계좌/시세)
import requests, time, math, datetime
from typing import Dict, Any, List, Optional, Tuple

from ..config import ALPACA_BASE_URL_LIVE, ALPACA_BASE_URL_PAPER, ALPACA_DATA_BASE_URL, DATA_FEED

ET = datetime.timezone(datetime.timedelta(hours=-5))

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
        
        # API 키 검증
        if not key or not secret:
            raise ValueError("API 키와 시크릿이 필요합니다")

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """공통 요청 처리 with 에러 핸들링"""
        headers = _headers(self.key, self.secret)
        if 'headers' in kwargs:
            headers.update(kwargs['headers'])
            del kwargs['headers']
        
        try:
            r = requests.request(method, url, headers=headers, timeout=15, **kwargs)
            if r.status_code == 401:
                raise Exception(f"인증 실패: API 키를 확인하세요 (paper={self.paper})")
            return r
        except requests.exceptions.RequestException as e:
            raise Exception(f"요청 실패: {str(e)}")

    # ---------- 계정/시장 ----------
    def get_account(self) -> Dict[str, Any]:
        url = f"{self.base_trading}/v2/account"
        r = self._request('GET', url)
        r.raise_for_status()
        return r.json()

    def get_clock(self) -> Dict[str, Any]:
        url = f"{self.base_trading}/v2/clock"
        r = self._request('GET', url)
        r.raise_for_status()
        return r.json()

    # ---------- 시세/바 ----------
    def get_latest_trade(self, symbol: str) -> Optional[float]:
        """최신 체결가 - 심볼 정규화"""
        # .SOXL -> SOXL 변환
        symbol = symbol.upper().lstrip('.')
        
        url = f"{self.base_data}/v2/stocks/{symbol}/trades/latest"
        params = {"feed": DATA_FEED}
        
        try:
            r = self._request('GET', url, params=params)
            if r.status_code != 200:
                return None
            data = r.json()
            trade = data.get("trade", {})
            return float(trade.get("p", 0)) if trade else None
        except Exception as e:
            print(f"시세 조회 실패 {symbol}: {e}")
            return None

    def get_daily_ohlc(self, symbol: str, limit: int = 2) -> Optional[List[Dict[str, Any]]]:
        """일봉 데이터"""
        symbol = symbol.upper().lstrip('.')
        
        url = f"{self.base_data}/v2/stocks/{symbol}/bars"
        params = {
            "timeframe": "1Day",
            "limit": limit,
            "feed": DATA_FEED,
            "adjustment": "raw"
        }
        
        try:
            r = self._request('GET', url, params=params)
            if r.status_code != 200:
                return None
            return r.json().get("bars", [])
        except Exception:
            return None

    def get_bars(self, symbol: str, timeframe: str = "15Min", limit: int = 100) -> Optional[List[Dict[str, Any]]]:
        """분봉 데이터"""
        symbol = symbol.upper().lstrip('.')
        
        url = f"{self.base_data}/v2/stocks/{symbol}/bars"
        params = {
            "timeframe": timeframe,
            "limit": limit,
            "feed": DATA_FEED,
            "adjustment": "raw"
        }
        
        try:
            r = self._request('GET', url, params=params)
            if r.status_code != 200:
                return None
            return r.json().get("bars", [])
        except Exception:
            return None

    # ---------- 주문/포지션 ----------
    def list_positions(self) -> List[Dict[str, Any]]:
        url = f"{self.base_trading}/v2/positions"
        try:
            r = self._request('GET', url)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"포지션 조회 실패: {e}")
            return []

    def list_orders(self, status: str = "open", limit: int = 50) -> List[Dict[str, Any]]:
        url = f"{self.base_trading}/v2/orders"
        params = {
            "status": status,
            "limit": limit,
            "nested": "true",
            "direction": "desc"
        }
        
        try:
            r = self._request('GET', url, params=params)
            r.raise_for_status()
            return r.json()
        except Exception:
            return []

    def cancel_order(self, order_id: str) -> bool:
        url = f"{self.base_trading}/v2/orders/{order_id}"
        try:
            r = self._request('DELETE', url)
            return r.status_code in (200, 204)
        except Exception:
            return False

    def submit_order(self,
                     symbol: str,
                     side: str,
                     qty: Optional[float] = None,
                     notional: Optional[float] = None,
                     type_: str = "limit",
                     time_in_force: str = "day",
                     limit_price: Optional[float] = None,
                     extended_hours: bool = False) -> Dict[str, Any]:
        
        # 심볼 정규화
        symbol = symbol.upper().lstrip('.')
        
        payload = {
            "symbol": symbol,
            "side": side,
            "type": type_,
            "time_in_force": time_in_force,
            "extended_hours": extended_hours,
        }
        
        if limit_price is not None:
            payload["limit_price"] = round(float(limit_price), 2)
        
        if qty is not None:
            # Alpaca는 소수점 9자리까지 지원
            payload["qty"] = str(round(float(qty), 9))
        elif notional is not None:
            payload["notional"] = str(round(float(notional), 2))
        else:
            return {"error": {"message": "qty 또는 notional이 필요합니다"}}

        url = f"{self.base_trading}/v2/orders"
        
        try:
            r = self._request('POST', url, json=payload)
            if r.status_code not in (200, 201):
                try:
                    error_data = r.json()
                    return {"error": error_data}
                except:
                    return {"error": {"message": r.text, "status": r.status_code}}
            return r.json()
        except Exception as e:
            return {"error": {"message": str(e)}}

    def get_activities(self, activity_types: str = "FILL", page_size: int = 50) -> List[Dict[str, Any]]:
        url = f"{self.base_trading}/v2/account/activities"
        params = {
            "activity_types": activity_types,
            "page_size": page_size,
            "direction": "desc"
        }
        
        try:
            r = self._request('GET', url, params=params)
            r.raise_for_status()
            return r.json()
        except Exception:
            return []