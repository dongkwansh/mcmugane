# -*- coding: utf-8 -*-
# 간단 지표 구현 (SMA/RSI/ATR)
from typing import List
import math

def sma(values: List[float], period: int) -> List[float]:
    if period <= 0:
        return []
    out = []
    acc = 0.0
    for i, v in enumerate(values):
        acc += v
        if i >= period:
            acc -= values[i - period]
        if i >= period - 1:
            out.append(acc / period)
        else:
            out.append(float('nan'))
    return out

def rsi(closes: List[float], period: int = 14) -> List[float]:
    if len(closes) < period + 1:
        return [float('nan')] * len(closes)
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i-1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_gain = sum(gains[1:period+1]) / period
    avg_loss = sum(losses[1:period+1]) / period
    rs_values = [float('nan')] * len(closes)
    rsi_values = [float('nan')] * len(closes)
    for i in range(period+1, len(closes)):
        avg_gain = (avg_gain * (period-1) + gains[i]) / period
        avg_loss = (avg_loss * (period-1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else float('inf')
        rs_values[i] = rs
        rsi_values[i] = 100 - (100 / (1 + rs))
    return rsi_values

def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    trs = []
    for i in range(len(closes)):
        if i == 0:
            trs.append(highs[i] - lows[i])
        else:
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            trs.append(tr)
    out = []
    acc = 0.0
    for i, tr in enumerate(trs):
        acc += tr
        if i >= period:
            acc -= trs[i - period]
        if i >= period - 1:
            out.append(acc / period)
        else:
            out.append(float('nan'))
    return out
