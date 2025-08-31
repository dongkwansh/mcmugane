from __future__ import annotations
import asyncio, json, uuid, logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from .broker import AlpacaBroker, AccountConfig
from .strategies import RuleStrategy, Signal

logger = logging.getLogger("engine")

@dataclass
class RunConfig:
    run_id: str
    account: AccountConfig
    symbols: List[str]
    strategy_spec: Dict[str, Any]
    sizing: Dict[str, Any]
    timeframe: str = "1Min"
    lookback_minutes: int = 120

@dataclass
class RunState:
    task: Optional[asyncio.Task] = None
    running: bool = False
    last_signal: Dict[str, str] = field(default_factory=dict)

class EngineManager:
    def __init__(self):
        self.runs: Dict[str, RunState] = {}
        self.cfgs: Dict[str, RunConfig] = {}

    def list_runs(self):
        return [{"run_id": rid, "running": st.running, "symbols": self.cfgs[rid].symbols if rid in self.cfgs else []}
                for rid, st in self.runs.items()]

    async def start(self, cfg: RunConfig, ws_send=None):
        if cfg.run_id in self.runs and self.runs[cfg.run_id].running:
            return
        state = RunState(running=True)
        self.runs[cfg.run_id] = state
        self.cfgs[cfg.run_id] = cfg
        state.task = asyncio.create_task(self._run_loop(cfg, state, ws_send))

    async def stop(self, run_id: str):
        st = self.runs.get(run_id)
        if st:
            st.running = False
            if st.task:
                st.task.cancel()
                try:
                    await st.task
                except asyncio.CancelledError:
                    pass
            del self.runs[run_id]
            self.cfgs.pop(run_id, None)

    async def _run_loop(self, cfg: RunConfig, state: RunState, ws_send=None):
        broker = AlpacaBroker(cfg.account)
        strat = RuleStrategy(cfg.strategy_spec)
        await self._notify(ws_send, f"[{cfg.run_id}] Engine started. Symbols={cfg.symbols}, TF={cfg.timeframe}")
        while state.running:
            try:
                df = broker.get_recent_bars(cfg.symbols, timeframe=cfg.timeframe, lookback_minutes=cfg.lookback_minutes)
                if df.empty:
                    await self._notify(ws_send, f"[{cfg.run_id}] No data returned; sleeping 10s")
                    await asyncio.sleep(10)
                    continue
                for sym in cfg.symbols:
                    sig: Signal = strat.evaluate_symbol(df, sym)
                    prev = state.last_signal.get(sym, None)
                    if sig.action in ("buy","sell") and prev == sig.action:
                        continue
                    if sig.action == "buy":
                        await self._execute(broker, sym, "buy", cfg, sig, ws_send)
                        state.last_signal[sym] = "buy"
                    elif sig.action == "sell":
                        await self._execute(broker, sym, "sell", cfg, sig, ws_send)
                        state.last_signal[sym] = "sell"
                await asyncio.sleep(55)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Engine loop error: %s", e)
                await self._notify(ws_send, f"[{cfg.run_id}] ERROR: {e}")
                await asyncio.sleep(5)
        await self._notify(ws_send, f"[{cfg.run_id}] Engine stopped.")

    async def _execute(self, broker: AlpacaBroker, symbol: str, side: str, cfg: RunConfig, sig: Signal, ws_send=None):
        order_kwargs = {}
        if cfg.sizing.get("type") == "qty":
            order_kwargs["qty"] = cfg.sizing.get("value", 1)
        else:
            order_kwargs["notional"] = cfg.sizing.get("value", 100.0)
        risk = cfg.strategy_spec.get("risk", {})
        take = risk.get("take_profit_percent")
        stop = risk.get("stop_loss_percent")
        price = sig.price or None
        if price:
            if take:
                order_kwargs["take_profit"] = round(price * (1 + (take/100.0) if side=='buy' else 1 - (take/100.0)), 2)
            if stop:
                order_kwargs["stop_loss"] = round(price * (1 - (stop/100.0) if side=='buy' else 1 + (stop/100.0)), 2)
        order = broker.market_order(symbol, side, tif="day", **order_kwargs)
        await self._notify(ws_send, f"Order {side.upper()} {symbol}: {json.dumps(order, default=str)[:300]}")

    async def _notify(self, ws_send, message: str):
        logger.info(message)
        if ws_send:
            try:
                await ws_send(message)
            except Exception:
                pass
