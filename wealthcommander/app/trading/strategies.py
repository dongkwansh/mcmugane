# -*- coding: utf-8 -*-
# 한글 주석: 5가지 대표 전략 구현 (단순/실용 위주)
import time, json, os
from typing import Dict, Any, List, Tuple, Optional
from .indicators import sma, rsi, atr

# 전략 타입:
# 1) sma_cross: 단순 이동평균 교차
# 2) rsi_reversion: RSI 과매도/과매수 반전
# 3) breakout_atr: ATR 기반 가격 돌파
# 4) vwap_pullback: VWAP 근접 반등(단순화: SMA 대용, 실제는 분봉 VWAP 필요)
# 5) trailing_stop: 추세 추적 + 트레일링 스탑

def decide_sma_cross(bars: List[Dict[str, Any]], fast: int, slow: int) -> str:
    closes = [b['c'] for b in bars]
    s_fast = sma(closes, fast)
    s_slow = sma(closes, slow)
    if len(closes) < slow + 2:
        return "hold"
    # 최근 2개 캔들에서 교차 확인
    cross_up = s_fast[-2] < s_slow[-2] and s_fast[-1] > s_slow[-1]
    cross_dn = s_fast[-2] > s_slow[-2] and s_fast[-1] < s_slow[-1]
    if cross_up:
        return "buy"
    if cross_dn:
        return "sell"
    return "hold"

def decide_rsi_reversion(bars: List[Dict[str, Any]], low_th: int, high_th: int) -> str:
    closes = [b['c'] for b in bars]
    r = rsi(closes, 14)
    val = r[-1] if r and r[-1] == r[-1] else None
    if val is None:
        return "hold"
    if val < low_th:
        return "buy"
    if val > high_th:
        return "sell"
    return "hold"

def decide_breakout_atr(bars: List[Dict[str, Any]], lookback: int, atr_mult: float) -> str:
    highs = [b['h'] for b in bars]
    lows = [b['l'] for b in bars]
    closes = [b['c'] for b in bars]
    if len(bars) < lookback + 1:
        return "hold"
    recent_high = max(highs[-lookback:])
    recent_low = min(lows[-lookback:])
    last_close = closes[-1]
    a = atr(highs, lows, closes, period=14)
    last_atr = a[-1] if a and a[-1] == a[-1] else None
    if last_atr is None:
        return "hold"
    if last_close > recent_high + atr_mult * last_atr:
        return "buy"
    if last_close < recent_low - atr_mult * last_atr:
        return "sell"
    return "hold"

def decide_vwap_pullback(bars: List[Dict[str, Any]], period: int, dev: float) -> str:
    # 간단화: SMA를 VWAP 근사로 사용 (실전은 분별 VWAP 필요)
    closes = [b['c'] for b in bars]
    s = sma(closes, period)
    if len(closes) < period + 2:
        return "hold"
    last = closes[-1]
    base = s[-1]
    if base != base:
        return "hold"
    # dev% 이내 접근 시 매수, dev% 하향 이탈 시 매도
    if last >= base * (1 - dev):
        return "buy"
    if last < base * (1 - 2*dev):
        return "sell"
    return "hold"

def decide_trailing_stop(bars: List[Dict[str, Any]], trail_pct: float) -> str:
    # 단순: 최근 N봉 최고/최저 기반 (진입/청산은 외부에서 관리)
    highs = [b['h'] for b in bars]
    lows = [b['l'] for b in bars]
    closes = [b['c'] for b in bars]
    if len(bars) < 20:
        return "hold"
    hh = max(highs[-20:])
    ll = min(lows[-20:])
    last = closes[-1]
    # 가격이 최근 고점 갱신하면 매수, 저점 근처면 매도
    if last > hh * (1.0 + 0.001):
        return "buy"
    if last < ll * (1.0 - 0.001):
        return "sell"
    return "hold"

def load_strategy_file(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def list_strategy_files(dir_path: str, prefix: str) -> List[str]:
    out = []
    if not os.path.isdir(dir_path):
        return out
    for n in sorted(os.listdir(dir_path)):
        if n.startswith(prefix) and n.endswith('.json'):
            out.append(n)
    return out

def decide_signal(strategy: Dict[str, Any], bars: List[Dict[str, Any]]) -> str:
    stype = strategy.get('strategy_type')
    params = strategy.get('params', {})
    if stype == 'sma_cross':
        return decide_sma_cross(bars, params.get('fast', 5), params.get('slow', 20))
    if stype == 'rsi_reversion':
        return decide_rsi_reversion(bars, params.get('low_th', 30), params.get('high_th', 70))
    if stype == 'breakout_atr':
        return decide_breakout_atr(bars, params.get('lookback', 20), params.get('atr_mult', 1.0))
    if stype == 'vwap_pullback':
        return decide_vwap_pullback(bars, params.get('period', 20), params.get('dev', 0.01))
    if stype == 'trailing_stop':
        return decide_trailing_stop(bars, params.get('trail_pct', 0.05))
    return 'hold'
