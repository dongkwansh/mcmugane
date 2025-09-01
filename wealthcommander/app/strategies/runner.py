# app/strategies/runner.py
import os
import json
import logging
from typing import Dict, Any
from app.alpaca_client import AlpacaBroker
from app.config import Settings
# core.utils에서 공용 함수 임포트
from app.core.utils import compute_qty_from_budget


logger = logging.getLogger("strategy")

class StrategyRunner:
    """Executes automated trading strategies."""
    def __init__(self, broker: AlpacaBroker, settings: Settings):
        self.broker = broker
        self.settings = settings
        self.is_running = False

    async def tick(self):
        """The main periodic task executed by the scheduler."""
        if self.is_running:
            logger.info("Previous strategy run is still in progress. Skipping this tick.")
            return

        self.is_running = True
        try:
            # These checks are now implicitly handled by the scheduler's paused state,
            # but double-checking here provides an extra layer of safety.
            if not self.settings.auto.enabled or not self.settings.auto.strategy:
                return

            if not self.broker.enabled or not self.broker.is_account_ok():
                logger.error("Alpaca connection is down or auth failed. Auto-trading skipped.")
                return

            await self.run_once()
        except Exception as e:
            logger.error(f"Unexpected error during strategy tick: {e}", exc_info=True)
        finally:
            self.is_running = False

    def load_strategy_config(self) -> Dict[str, Any]:
        """Loads the configuration file for the currently active strategy."""
        strategy_name = self.settings.auto.strategy
        filepath = os.path.join("config", "strategies", f"{strategy_name}.json")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Strategy file not found: {strategy_name}")
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    async def run_once(self):
        """Executes a single run of the active strategy."""
        try:
            strategy = self.load_strategy_config()
        except Exception as e:
            logger.error(f"Failed to load strategy config: {e}")
            return

        if not strategy.get("enabled", False):
            logger.info(f"Strategy '{strategy['name']}' is disabled, skipping.")
            return

        logger.info(f"Executing strategy: '{strategy['name']}'")
        
        # In a real-world scenario, you would dispatch to different execution
        # methods based on `strategy['type']`.
        await self.execute_simple_buy_strategy(strategy)

    async def execute_simple_buy_strategy(self, strategy: Dict[str, Any]):
        """A placeholder execution logic that performs a simple buy."""
        try:
            bp = self.broker.buying_power()
            if bp < 1.0:
                logger.warning(f"Insufficient buying power (${bp:.2f}). Cannot execute strategy.")
                return

            sizing = strategy.get("position_sizing", {})
            sizing_type = sizing.get("type", "bp_percent")
            sizing_value = float(sizing.get("value", 1.0))

            budget = 0
            if sizing_type == "bp_percent":
                budget = bp * (sizing_value / 100.0)
            elif sizing_type == "fixed_notional":
                budget = min(bp, sizing_value)

            universe = strategy.get("universe", [])
            if not universe:
                logger.warning("Strategy universe is empty. Nothing to trade.")
                return

            budget_per_symbol = budget / len(universe) if universe else 0
            logger.info(f"Total budget for this run: ${budget:.2f}, Per-symbol budget: ${budget_per_symbol:.2f}")

            for symbol in universe:
                await self.place_order_for_symbol(symbol, budget_per_symbol)

        except Exception as e:
            logger.error(f"Error in strategy '{strategy['name']}': {e}", exc_info=True)

    async def place_order_for_symbol(self, symbol: str, budget: float):
        """Fetches price and places a market buy order for a single symbol."""
        try:
            price = self.broker.latest_price(symbol)
            if not price or price <= 0:
                logger.warning(f"{symbol}: Could not fetch price. Skipping order.")
                return

            qty = compute_qty_from_budget(price, budget, self.settings.allow_fractional)
            if qty <= 0:
                return

            order = self.broker.submit_order(symbol, qty, "buy", "market")
            logger.info(f"Order submitted: BUY {qty} of {symbol} @ market. [ID: {order.id}]")

        except Exception as e:
            logger.error(f"Failed to place order for {symbol}: {e}")