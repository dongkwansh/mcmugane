from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import pandas as pd
from .indicators import sma, ema, rsi, macd, vwap, donchian_channel

@dataclass
class Signal:
    symbol: str
    action: str  # 'buy', 'sell', 'hold'
    reason: str
    price: Optional[float] = None

class RuleStrategy:
    def __init__(self, spec: Dict[str, Any]):
        self.spec = spec
        self.timeframe = spec.get("timeframe", "1Min")
        self.params = spec.get("params", {})
        self.risk = spec.get("risk", {})
        self.name = spec.get("name", "Unnamed")

    def _build_features(self, df_sym: pd.DataFrame) -> pd.DataFrame:
        df = df_sym.sort_values("timestamp").copy()
        df['sma_fast'] = sma(df['close'], int(self.params.get("sma_fast", 10)))
        df['sma_slow'] = sma(df['close'], int(self.params.get("sma_slow", 30)))
        df['ema_fast'] = ema(df['close'], int(self.params.get("ema_fast", 12)))
        df['ema_slow'] = ema(df['close'], int(self.params.get("ema_slow", 26)))
        df['rsi'] = rsi(df['close'], int(self.params.get("rsi_period", 14)))
        m_line, s_line, hist = macd(df['close'],
                                    int(self.params.get("macd_fast", 12)),
                                    int(self.params.get("macd_slow", 26)),
                                    int(self.params.get("macd_signal", 9)))
        df['macd_line'] = m_line
        df['macd_signal'] = s_line
        df['vwap'] = vwap(df[['high','low','close','volume']])
        upper, lower = donchian_channel(df['high'], df['low'], int(self.params.get("donchian", 20)))
        df['donchian_high'] = upper
        df['donchian_low'] = lower
        return df

    def _last_cross(self, a: pd.Series, b: pd.Series) -> str:
        if len(a) < 2 or len(b) < 2:
            return ""
        prev = a.iloc[-2] - b.iloc[-2]
        now = a.iloc[-1] - b.iloc[-1]
        if prev < 0 and now > 0:
            return "crosses_above"
        if prev > 0 and now < 0:
            return "crosses_below"
        return ""

    def evaluate_symbol(self, df: pd.DataFrame, symbol: str) -> Signal:
        d = df[df['symbol'] == symbol]
        if d.empty or len(d) < 35:
            return Signal(symbol, "hold", "insufficient_data")
        d = self._build_features(d)

        for rule in self.spec.get("entry_rules", []):
            typ = rule.get("type")
            if typ == "crosses_above":
                left = d[rule['left'].get('feature','sma_fast')]
                right = d[rule['right'].get('feature','sma_slow')]
                if self._last_cross(left, right) == "crosses_above":
                    return Signal(symbol, "buy", f"{rule.get('note','cross_above')}", price=float(d['close'].iloc[-1]))
            elif typ == "rsi_below":
                thresh = float(rule.get("threshold", 30))
                if d['rsi'].iloc[-1] < thresh:
                    return Signal(symbol, "buy", f"rsi<{thresh}", price=float(d['close'].iloc[-1]))
            elif typ == "breakout_high":
                look = int(rule.get("lookback", 20))
                if d['close'].iloc[-1] >= d['donchian_high'].iloc[-1]:
                    return Signal(symbol, "buy", f"breakout_{look}", price=float(d['close'].iloc[-1]))
            elif typ == "vwap_reversion_long":
                if d['close'].iloc[-1] < d['vwap'].iloc[-1]:
                    return Signal(symbol, "buy", "price_below_vwap", price=float(d['close'].iloc[-1]))

        for rule in self.spec.get("exit_rules", []):
            typ = rule.get("type")
            if typ == "crosses_below":
                left = d[rule['left'].get('feature','sma_fast')]
                right = d['sma_slow']
                if self._last_cross(left, right) == "crosses_below":
                    return Signal(symbol, "sell", f"{rule.get('note','cross_below')}", price=float(d['close'].iloc[-1]))
            elif typ == "rsi_above":
                thresh = float(rule.get("threshold", 70))
                if d['rsi'].iloc[-1] > thresh:
                    return Signal(symbol, "sell", f"rsi>{thresh}", price=float(d['close'].iloc[-1]))
            elif typ == "breakdown_low":
                look = int(rule.get("lookback", 20))
                if d['close'].iloc[-1] <= d['donchian_low'].iloc[-1]:
                    return Signal(symbol, "sell", f"breakdown_{look}", price=float(d['close'].iloc[-1]))
            elif typ == "vwap_reversion_exit":
                if d['close'].iloc[-1] > d['vwap'].iloc[-1]:
                    return Signal(symbol, "sell", "price_above_vwap", price=float(d['close'].iloc[-1]))

        return Signal(symbol, "hold", "no_rule_trigger")
