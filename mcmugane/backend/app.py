import re
from typing import Dict, Any, Optional
from alpaca_client import AlpacaClient
import json

class TerminalCommands:
    def __init__(self, alpaca_client: AlpacaClient, config_manager):
        self.alpaca = alpaca_client
        self.config = config_manager
        self.mode = "PAPER"
        self.auto_trading = False
        
    def parse_command(self, command: str) -> Dict[str, Any]:
        """터미널 명령어 파싱 및 실행"""
        cmd_parts = command.strip().upper().split()
        
        if not cmd_parts:
            return {"error": "명령어를 입력하세요"}
        
        base_cmd = cmd_parts[0]
        
        # 명령어 매핑
        commands = {
            "HELP": self.show_help,
            "MODE": self.set_mode,
            "AUTO": self.set_auto,
            "STATUS": self.show_status,
            "PORTFOLIO": self.show_portfolio,
            "BUY": self.buy_interactive,
            "SELL": self.sell_interactive,
            "CANCEL": self.cancel_order,
            "ORDERS": self.show_orders,
            "HISTORY": self.show_history,
            "LOGS": self.show_logs
        }
        
        # 티커 조회 (.TICKER 형식)
        if base_cmd.startswith('.'):
            return self.show_ticker_info(base_cmd[1:])
        
        if base_cmd in commands:
            return commands[base_cmd](cmd_parts[1:] if len(cmd_parts) > 1 else [])
        
        return {"error": f"알 수 없는 명령어: {base_cmd}"}
    
    def buy_interactive(self, args: list) -> Dict[str, Any]:
        """대화형 매수 처리"""
        # args 길이에 따른 처리
        if len(args) == 0:
            return {
                "interactive": True,
                "step": "ticker",
                "message": "매수할 종목을 입력하세요 (예: .AAPL):"
            }
        
        ticker = args[0]
        if ticker.startswith('.'):
            ticker = ticker[1:]
        
        # myETF 처리
        if ticker.startswith('MYETF'):
            return self.buy_etf_portfolio(ticker, args[1] if len(args) > 1 else None)
        
        # 수량 처리
        if len(args) == 1:
            return {
                "interactive": True,
                "step": "quantity",
                "ticker": ticker,
                "message": f"{ticker} 몇 주를 매수하시겠습니까? (숫자, %, 또는 $금액):"
            }
        
        quantity = self.parse_quantity(args[1], ticker, "buy")
        
        # 가격 처리
        if len(args) == 2:
            return {
                "interactive": True,
                "step": "price",
                "ticker": ticker,
                "quantity": quantity,
                "message": f"{ticker} {quantity}주를 어떤 가격에 매수하시겠습니까? (Enter=시장가):"
            }
        
        price = args[2] if args[2] != "MARKET" else None
        
        return self.execute_buy(ticker, quantity, price)
    
    def parse_quantity(self, qty_str: str, ticker: str, action: str) -> int:
        """수량 파싱 (%, $, 숫자)"""
        if qty_str.endswith('%'):
            percentage = float(qty_str[:-1]) / 100
            if action == "buy":
                buying_power = self.alpaca.get_buying_power()
                current_price = self.alpaca.get_current_price(ticker)
                return int((buying_power * percentage) / current_price)
            else:  # sell
                position = self.alpaca.get_position(ticker)
                return int(position.qty * percentage)
        
        elif qty_str.startswith('$'):
            amount = float(qty_str[1:])
            current_price = self.alpaca.get_current_price(ticker)
            return int(amount / current_price)
        
        else:
            return int(qty_str)
    
def show_help(self, args: list) -> Dict[str, Any]:
    """도움말 표시"""
    help_text = """
╔════════════════════════════════════════════════════════════════╗
║               McMugane Terminal - Help                         ║
╠════════════════════════════════════════════════════════════════╣
║ BASIC COMMANDS:                                                ║
║   HELP              - Show this help message                   ║
║   MODE {PAPER|LIVE} - Switch trading mode                      ║
║   AUTO {ON|OFF}     - Toggle auto-trading                      ║
║   STATUS            - Show system & account status             ║
║   PORTFOLIO         - Display current holdings                 ║
║   LOCALE {US|KO}    - Switch language/timezone                 ║
║                                                                 ║
║ MARKET INFO:                                                   ║
║   MARKET            - Show market status & hours               ║
║   .{TICKER}         - Get stock info (e.g., .AAPL)            ║
║   QUOTE {TICKER}    - Get detailed quote                       ║
║                                                                 ║
║ TRADING COMMANDS:                                              ║
║   BUY [.TICKER] [QTY] [PRICE]  - Buy stock (interactive)      ║
║   SELL [.TICKER] [QTY] [PRICE] - Sell stock (interactive)     ║
║   CANCEL {ORDER_ID}             - Cancel pending order         ║
║                                                                 ║
║ QUANTITY FORMATS:                                              ║
║   10        - Buy/Sell 10 shares                              ║
║   20%       - 20% of buying power (BUY) or position (SELL)    ║
║   $500      - $500 worth of shares                            ║
║                                                                 ║
║ ETF PORTFOLIOS:                                                ║
║   BUY myETF1 $5000  - Buy ETF portfolio with $5000            ║
║   SELL myETF1 50%   - Sell 50% of ETF holdings               ║
║   REBALANCE myETF1  - Rebalance to target allocation          ║
║                                                                 ║
║ HISTORY & LOGS:                                                ║
║   ORDERS            - Show pending orders                      ║
║   HISTORY [DAYS]    - Show trade history                       ║
║   LOGS [DATE]       - View logs (YYYYMMDD or MM/DD/YYYY)      ║
║                                                                 ║
║ ADVANCED:                                                       ║
║   SCAN {STRATEGY}   - Scan for opportunities                   ║
║   BACKTEST {STRAT}  - Run strategy backtest                    ║
║   PERF [PERIOD]     - Performance report                       ║
║   EXPORT {TYPE}     - Export data (CSV/JSON)                   ║
╚════════════════════════════════════════════════════════════════╝

Trading Hours (Eastern Time):
  Pre-Market:    4:00 AM -  9:30 AM ET
  Regular:       9:30 AM -  4:00 PM ET  
  After-Hours:   4:00 PM -  8:00 PM ET

Type any command to get started. Commands are not case-sensitive.
        """
    return {"success": True, "message": help_text}