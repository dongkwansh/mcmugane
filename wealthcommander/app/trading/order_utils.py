# -*- coding: utf-8 -*-
# 한글 주석: 주문 관련 수량/금액 계산 유틸
from typing import Tuple, Optional

def parse_size_token(token: str) -> Tuple[str, float]:
    """크기 토큰 파싱
    - '20'   => ("shares", 20)
    - '20%'  => ("percent", 20)
    - '$20'  => ("notional", 20)
    """
    token = token.strip().lower()
    if token.endswith('%'):
        return ("percent", float(token[:-1]))
    if token.startswith('$'):
        return ("notional", float(token[1:]))
    return ("shares", float(token))

def compute_from_percent(buying_power: float, percent: float, price: float) -> float:
    """비율(%)과 현재가로 주수 계산"""
    notional = buying_power * (percent / 100.0)
    if price <= 0:
        return 0.0
    shares = notional / price
    return round(shares, 4)

def compute_from_notional(amount: float, price: float) -> float:
    if price <= 0:
        return 0.0
    return round(amount / price, 4)
