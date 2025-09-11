# -*- coding: utf-8 -*-
# 한글 주석: 자동매매 실행/상태 관리
import asyncio, json, os, datetime
from typing import Dict, Any, List, Optional
from .alpaca_client import AlpacaClient
from .strategies import load_strategy_file, decide_signal
from .order_utils import compute_from_notional
from ..config import AUTO_METHODS_DIR

class AutoBot:
    def __init__(self, client: AlpacaClient, send_status_cb):
        self.client = client
        self.send_status = send_status_cb  # UI로 상태 출력 콜백
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._strategy_path: Optional[str] = None
        self._strategy: Optional[Dict[str, Any]] = None

    def is_running(self) -> bool:
        return self._running

    def current_strategy_name(self) -> str:
        if not self._strategy:
            return "(없음)"
        return self._strategy.get('name', os.path.basename(self._strategy_path or ''))

    async def start(self, strategy_file: str):
        if self._running:
            return
        self._strategy_path = os.path.join(AUTO_METHODS_DIR, strategy_file)
        self._strategy = load_strategy_file(self._strategy_path)
        self._running = True
        self.send_status(f"자동매매 시작: {self.current_strategy_name()}")
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.send_status("자동매매 중지")

    async def _run(self):
        # 매우 단순한 루프: 전략 유니버스 심볼을 순회하며 시그널 판단->주문
        try:
            while self._running and self._strategy:
                tf = self._strategy.get('timeframe', '15Min')
                universe = [s.lstrip('.') for s in self._strategy.get('universe', [])]
                risk = self._strategy.get('risk', {})
                order_cfg = self._strategy.get('order', {})
                max_notional = float(risk.get('max_notional_per_symbol', 1000))
                tif = order_cfg.get('time_in_force', 'day')
                ext = bool(self._strategy.get('extended_hours', False))

                for sym in universe:
                    if not self._running:
                        break
                    bars = self.client.get_bars(sym, timeframe=tf, limit=100) or []
                    if len(bars) < 30:
                        continue
                    sig = decide_signal(self._strategy, bars)
                    last = bars[-1]['c']
                    # 단순 예시: buy => max_notional 만큼, sell => 보유분 전량 매도
                    if sig == 'buy':
                        qty = compute_from_notional(max_notional, last)
                        resp = self.client.submit_order(symbol=sym, side='buy', qty=qty,
                                                        type_='limit', time_in_force=tif,
                                                        limit_price=last, extended_hours=ext)
                        sid = resp.get('id') or resp.get('error', {}).get('message', 'ERR')
                        self.send_status(f"[{datetime.datetime.now():%m-%d %I:%M%p}] {sym} {qty}주 매수 시도 (limit {last}) => {sid}")
                    elif sig == 'sell':
                        # 포지션 조회 후 해당 심볼만 매도
                        positions = self.client.list_positions()
                        target = next((p for p in positions if p.get('symbol') == sym), None)
                        if target:
                            qty = float(target.get('qty', '0'))
                            if qty > 0:
                                resp = self.client.submit_order(symbol=sym, side='sell', qty=qty,
                                                                type_='limit', time_in_force=tif,
                                                                limit_price=last, extended_hours=ext)
                                sid = resp.get('id') or resp.get('error', {}).get('message', 'ERR')
                                self.send_status(f"[{datetime.datetime.now():%m-%d %I:%M%p}] {sym} {qty}주 매도 시도 (limit {last}) => {sid}")
                await asyncio.sleep(30)  # 30초 주기 (예시)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.send_status(f"자동매매 오류: {e}")
        finally:
            self._running = False
