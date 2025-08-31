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
McMugane Terminal 명령어 도움말
================================
기본 명령어:
  HELP              - 이 도움말 표시
  MODE {PAPER|LIVE} - 거래 모드 변경
  AUTO {ON|OFF}     - 자동매매 켜기/끄기
  STATUS            - 현재 상태 표시
  PORTFOLIO         - 보유 종목 표시
  
종목 조회:
  .{TICKER}         - 종목 정보 조회 (예: .AAPL)
  
매매 명령:
  BUY [.TICKER] [수량] [가격]  - 매수 (대화형 지원)
  SELL [.TICKER] [수량] [가격] - 매도 (대화형 지원)
  CANCEL {ORDER_ID}            - 주문 취소
  
수량 입력 방식:
  10        - 10주
  20%       - Buying Power의 20% (매수) 또는 보유수량의 20% (매도)
  $500      - $500 어치
  
ETF 포트폴리오:
  BUY myETF1 $5000  - myETF1 구성으로 $5000 매수
  SELL myETF1 50%   - myETF1 구성 종목들 50% 매도
  
조회 명령:
  ORDERS            - 미체결 주문 조회
  HISTORY           - 거래 내역 조회
  LOGS {DATE}       - 로그 조회
        """
        return {"success": True, "message": help_text}