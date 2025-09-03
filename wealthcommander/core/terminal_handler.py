"""
Terminal Command Handler - Optimized and Simplified
"""

import asyncio
import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime
from .config_manager import ConfigManager
from .logging_system import log_user_activity, log_trading, log_error

logger = logging.getLogger(__name__)
trading_logger = logging.getLogger('trading')

class TerminalHandler:
    """통합 터미널 명령어 처리기 - 단순화된 구조"""
    
    def __init__(self, broker, strategy_runner, ws_manager, scheduler):
        self.broker = broker
        self.strategy_runner = strategy_runner
        self.ws_manager = ws_manager
        self.scheduler = scheduler
        self.config_manager = ConfigManager()
        
        self.interactive_sessions = {}
        
        self.commands = {
            "HELP": self._cmd_help,
            "HISTORY": self._cmd_history,
            "STATUS": self._cmd_status,
            "PORTFOLIO": self._cmd_portfolio,
            "POSITIONS": self._cmd_portfolio,
            "ORDERS": self._cmd_orders,
            "BUY": self._cmd_buy,
            "SELL": self._cmd_sell,
            "CANCEL": self._cmd_cancel,
            "AUTO": self._cmd_auto,
            "STOP": self._cmd_stop_auto,
            "START": self._cmd_start_auto,
            "ACCOUNT": self._cmd_account,
        }
    
    def update_broker(self, new_broker):
        self.broker = new_broker
    
    async def process_command(self, command: str, client_id: Optional[str] = None) -> str:
        try:
            parts = command.strip().split()
            if not parts:
                return ""

            main_cmd = parts[0].upper()
            cmd_args = parts[1:]

            log_user_activity("user_command", 
                            session_id=client_id,
                            command=command,
                            command_upper=main_cmd,
                            timestamp_start=datetime.now().isoformat())
            
            logger.info(f"Command received: '{command}' from client {client_id}")
            
            if client_id and client_id in self.interactive_sessions:
                logger.info(f"Interactive mode handling for client {client_id}")
                result = await self._handle_interactive(client_id, command)
                log_user_activity("interactive_response",
                                session_id=client_id,
                                command=command,
                                response_length=len(result),
                                mode=self.interactive_sessions.get(client_id, {}).get('mode', 'unknown'))
                return result

            if main_cmd in self.commands:
                handler_func = self.commands[main_cmd]
                
                # Pass arguments correctly
                if main_cmd in ['BUY', 'START', 'STOP']:
                    result = await handler_func(client_id)
                elif main_cmd == 'ACCOUNT':
                    result = await handler_func(*cmd_args) # Pass arguments to account handler
                else:
                    result = await handler_func()
                
                log_user_activity("command_completed",
                                session_id=client_id,
                                command=command,
                                success=True,
                                response_length=len(result) if result else 0,
                                timestamp_end=datetime.now().isoformat())
                return result
            
            if command.startswith('.') and len(command.split()) == 1:
                symbol = command[1:].upper()
                return await self._cmd_stock_info(symbol)
            
            if not command.startswith('.') and command.isalpha():
                etfs = self.config_manager.get_etfs()
                if command.upper() in etfs:
                    if client_id:
                        self.interactive_sessions[client_id] = {
                            'mode': 'etf_buy',
                            'etf_name': command.upper()
                        }
                        return self.config_manager.get_message('etf_prompt', etf_name=command.upper())
                    return self.config_manager.get_message('etf_mode_not_supported', command=command.upper())
            
                if len(command) >= 2:
                    return self.config_manager.get_message('unknown_command_with_hint', command=command)
            
            if main_cmd in ["BUY", "SELL"]:
                if len(parts) >= 2 and parts[1].startswith('.'):
                    symbol = parts[1][1:].upper()
                    if client_id:
                        self.interactive_sessions[client_id] = {'mode': 'quick_buy', 'symbol': symbol}
                    return self.config_manager.get_message('quick_buy_prompt', symbol=symbol)
                
                return await self._parse_trade_command(command, client_id)
            
            return self.config_manager.get_message('unknown_command', command=command)
            
        except Exception as e:
            logger.error(self.config_manager.get_message('command_parse_error', error=str(e)))
            return self.config_manager.get_message('command_error', error=str(e))
    
    async def _cmd_help(self) -> str:
        """도움말"""
        return self.config_manager.get_message('help_text')
    
    async def _cmd_history(self) -> str:
        """거래 내역"""
        try:
            orders = await self.broker.get_orders()
            if not orders:
                return self.config_manager.get_message('no_trading_history')
            
            result = self.config_manager.get_message('trading_history_header')
            for order in orders[-10:]:  # 최근 10개만 표시
                status = self.config_manager.get_message('order_filled_icon') if order.get('status') == 'filled' else self.config_manager.get_message('order_pending_icon')
                result += f"{status} {order.get('side', '')} {order.get('symbol', '')} "
                result += f"{order.get('qty', 0)}주 @ ${order.get('filled_avg_price', 0):.2f}\\n"
            
            return result
        except Exception as e:
            logger.error(self.config_manager.get_message('history_query_error', error=str(e)))
            return self.config_manager.get_message('history_failed', error=str(e))
    
    async def _cmd_status(self) -> str:
        try:
            account_info = await self.broker.get_account_info()
            market_status = await self.broker.get_market_status()
            auto_status = self.strategy_runner.get_status()
            
            # Use message keys for all text parts
            result = self.config_manager.get_message('headers.status_header')
            result += self.config_manager.get_message('status.account_number', account=account_info.get('account_number', 'N/A')) + "\n"
            result += self.config_manager.get_message('status.current_account_info', account=self.config_manager.get_current_account()) + "\n"
            result += self.config_manager.get_message('status.default_account_info', account=self.config_manager.get_default_account()) + "\n"
            result += self.config_manager.get_message('status.total_value', value=account_info.get('portfolio_value', 0)) + "\n"
            result += self.config_manager.get_message('status.buying_power', value=account_info.get('buying_power', 0)) + "\n"
            result += self.config_manager.get_message('status.cash_value', value=account_info.get('cash', 0)) + "\n"
            
            market_open_msg_key = 'status.market_open_status' if market_status.get('is_open') else 'status.market_closed_status'
            result += self.config_manager.get_message('status.market_status', status=self.config_manager.get_message(market_open_msg_key)) + "\n"
            
            auto_running_msg_key = 'status.auto_running_status' if auto_status.get('enabled') else 'status.auto_stopped_status'
            result += self.config_manager.get_message('status.auto_trading_status', status=self.config_manager.get_message(auto_running_msg_key)) + "\n"
            
            return result
            
        except Exception as e:
            return self.config_manager.get_message('system.status_failed', error=str(e))

    async def _cmd_portfolio(self) -> str:
        """포트폴리오 조회"""
        try:
            positions = await self.broker.get_positions()
            
            if not positions:
                return self.config_manager.get_message('system.no_positions')
            
            result = self.config_manager.get_message('headers.portfolio_main_header')
            
            # Note: This part has complex formatting that is better left in code
            # rather than being moved to messages.json
            header_format = "{:<8} {:<10} {:<15} {:<15} {:<10}\n"
            result += header_format.format("Symbol", "Qty", "Market Value", "P&L", "P&L (%)")
            result += "-" * 60 + "\n"

            total_value = 0
            total_pl = 0
            
            for pos in positions:
                market_value = float(pos['market_value'])
                unrealized_pl = float(pos['unrealized_pl'])
                total_value += market_value
                total_pl += unrealized_pl
                
                row_format = "{:<8} {:<10.2f} ${:<14,.2f} ${:<14,.2f} {:<9.2f}%\n"
                result += row_format.format(
                    pos['symbol'],
                    float(pos['qty']),
                    market_value,
                    unrealized_pl,
                    float(pos['unrealized_plpc']) * 100
                )
            
            result += "-" * 60 + "\n"
            result += f"Total Value: ${total_value:,.2f}, Total P&L: ${total_pl:,.2f}"
            
            return result
            
        except Exception as e:
            return self.config_manager.get_message('system.portfolio_failed', error=str(e))

    async def _cmd_orders(self) -> str:
        """주문 내역"""
        try:
            orders = await self.broker.get_orders(limit=10)
            
            if not orders:
                return self.config_manager.get_message('system.no_orders')
            
            result = self.config_manager.get_message('headers.orders_main_header')
            header_format = "{:<8} {:<6} {:<8} {:<12} {:<10} {:<20}\n"
            result += header_format.format("Symbol", "Side", "Qty", "Price", "Status", "Created At")
            result += "-" * 68 + "\n"
            
            for order in orders:
                price = f"${order['limit_price']:.2f}" if order['limit_price'] else "Market"
                created_time = order['created_at'].split('.')[0] if order['created_at'] else "N/A"

                row_format = "{:<8} {:<6} {:<8.0f} {:<12} {:<10} {:<20}\n"
                result += row_format.format(
                    order['symbol'],
                    order['side'],
                    float(order['qty']),
                    price,
                    order['status'],
                    created_time.replace("T", " ")
                )
            
            return result
            
        except Exception as e:
            return self.config_manager.get_message('system.orders_failed', error=str(e))
    
    async def _cmd_buy(self, client_id: Optional[str] = None) -> str:
        """매수 명령어 (대화형)"""
        if client_id:
            self.interactive_sessions[client_id] = {
                'mode': 'buy_symbol',
                'step': 'symbol'
            }
        return self.config_manager.get_message('buy_symbol_prompt')
    
    async def _cmd_sell(self) -> str:
        """매도 명령어 (대화형)"""
        return self.config_manager.get_message('sell_symbol_prompt')
    
    async def _cmd_stock_info(self, symbol: str) -> str:
        """종목 정보 조회"""
        try:
            # 현재 시세 조회
            quote = await self.broker.get_quote(symbol)
            
            # 포지션 조회
            positions = await self.broker.get_positions()
            position = None
            for pos in positions:
                if pos.get('symbol') == symbol:
                    position = pos
                    break
            
            # Alpaca API 없이도 기본 정보 표시
            result = f"\n📊 {symbol} 종목 정보\n==============================\n"
            result += "💰 현재가: 시장 마감 (API 연결 필요)\n"
            result += "📈 매수호가: --\n"
            result += "📉 매도호가: --\n"
            result += "\n📭 보유하지 않음\n"
            
            return result
            
        except Exception as e:
            return self.config_manager.get_message('symbol_info_query_failed', error=str(e))
    
    async def _cmd_cancel(self) -> str:
        """주문 취소"""
        try:
            cancelled_count = await self.broker.cancel_all_orders()
            return self.config_manager.get_message('orders_cancelled', count=cancelled_count)
        except Exception as e:
            return self.config_manager.get_message('cancel_failed', error=e)
    
    async def _cmd_auto(self) -> str:
        """자동매매 상태"""
        try:
            status = self.strategy_runner.get_status()
            
            result = self.config_manager.get_message('auto_status_header')
            
            if status.get('enabled'):
                result += self.config_manager.get_message('auto_enabled') + "\\n"
                result += self.config_manager.get_message('auto_strategy_info', strategy=status.get('strategy', 'N/A'))
                result += self.config_manager.get_message('auto_interval_info', interval=status.get('interval', 'N/A'))
                result += self.config_manager.get_message('auto_next_run_info', next_run=status.get('next_run', 'N/A'))
            else:
                result += self.config_manager.get_message('auto_disabled') + "\\n"
                result += self.config_manager.get_message('auto_start_info') + "\\n"
            
            return result
            
        except Exception as e:
            return self.config_manager.get_message('auto_status_failed', error=e)
    
    async def _cmd_start_auto(self, client_id: Optional[str] = None) -> str:
        """자동매매 시작"""
        try:
            # 자동매매 설정 조회
            auto_config = self.config_manager.get_auto_trading_config()
            if not auto_config:
                return self.config_manager.get_message('auto_config_not_found')
            
            # 설정 내용 표시
            config_display = self.config_manager.get_message('auto_config_display',
                strategy=auto_config.get('strategy', 'N/A'),
                interval=auto_config.get('interval', 'N/A'),
                account=self.config_manager.get_current_account(),
                max_investment=auto_config.get('max_investment_percent', 100),
                rebalancing='사용' if auto_config.get('rebalancing_enabled', False) else '비활성화'
            )
            
            # 확인 메시지 대화형 모드 설정
            if client_id:
                self.interactive_sessions[client_id] = {
                    'mode': 'auto_start_confirm',
                    'auto_config': auto_config
                }
            
            return self.config_manager.get_message('auto_config_confirmation', config=config_display)
            
        except Exception as e:
            return self.config_manager.get_message('auto_start_failed', error=e)
    
    async def _cmd_stop_auto(self, client_id: Optional[str] = None) -> str:
        """자동매매 중지"""
        try:
            # 현재 상태 확인
            status = self.strategy_runner.get_status()
            if not status.get('enabled'):
                return self.config_manager.get_message('auto_not_running')
            
            # 대화형 모드 설정
            if client_id:
                self.interactive_sessions[client_id] = {
                    'mode': 'auto_stop_confirm',
                    'current_status': status
                }
            
            return self.config_manager.get_message('auto_stop_confirmation',
                strategy=status.get('strategy', 'N/A'),
                interval=status.get('interval', 'N/A')
            )
            
        except Exception as e:
            return self.config_manager.get_message('auto_stop_failed', error=e)
    
    async def _cmd_account(self, *args) -> str:
        try:
            if not args:
                # Display account status
                current_account = self.config_manager.get_current_account()
                default_account = self.config_manager.get_default_account()
                available_accounts = self.config_manager.get_available_accounts()
                account_info = await self.broker.get_account_info()

                result = self.config_manager.get_message("account.header")
                result += self.config_manager.get_message("account.current_account", account=current_account)
                result += self.config_manager.get_message("account.default_account", account=default_account)
                result += self.config_manager.get_message("account.available_accounts", accounts=', '.join(available_accounts))
                
                if account_info:
                    result += self.config_manager.get_message("account.total_assets", total_assets=f"${account_info.get('portfolio_value', 0):,.2f}")
                    result += self.config_manager.get_message("account.buying_power", buying_power=f"${account_info.get('buying_power', 0):,.2f}")
                    result += self.config_manager.get_message("account.cash", cash=f"${account_info.get('cash', 0):,.2f}")

                result += self.config_manager.get_message("account.usage_guide_header")
                result += self.config_manager.get_message("account.usage_guide_live")
                result += self.config_manager.get_message("account.usage_guide_paper1")
                result += self.config_manager.get_message("account.usage_guide_paper2")
                result += self.config_manager.get_message("account.usage_guide_paper3")
                
                return result
            
            target_account = args[0].upper()
            available_accounts = self.config_manager.get_available_accounts()
            
            if target_account not in available_accounts:
                return self.config_manager.get_message("account.switch_invalid", 
                                                   account=target_account, 
                                                   available=', '.join(available_accounts))
            
            self.config_manager.switch_account(target_account)
            await self.broker.initialize()
            return self.config_manager.get_message("account.switch_success", account=target_account)
            
        except Exception as e:
            return self.config_manager.get_message("account.command_error", error=str(e))
            
    async def _parse_trade_command(self, command: str, client_id: Optional[str] = None) -> str:
        """거래 명령어 파싱"""
        try:
            parts = command.strip().split()
            
            if len(parts) < 2:
                return self.config_manager.get_message('invalid_format')
            
            action = parts[0].upper()
            symbol = parts[1].upper()
            
            # SELL ALL 처리
            if action == "SELL" and symbol == "ALL":
                return await self._handle_sell_all(client_id)
            
            # myETF 확인 (BUY TICKER 형식)
            if action == "BUY" and len(parts) >= 2:
                import json
                try:
                    with open('config/myETFs.json', 'r', encoding='utf-8') as f:
                        etf_data = json.load(f)
                    
                    if symbol in etf_data['custom_etfs']:
                        return await self._handle_etf_buy(symbol, parts[2:] if len(parts) > 2 else [], client_id)
                except FileNotFoundError:
                    pass
            
            # 일반 주식 거래 처리
            return await self._handle_stock_trade(action, symbol, parts[2:] if len(parts) > 2 else [], client_id)
            
        except ValueError:
            return self.config_manager.get_message('invalid_amount_format')
        except Exception as e:
            logger.error(f"거래 명령어 파싱 오류: {e}")
            return self.config_manager.get_message('order_execution_failed', error=e)
    
    async def _handle_stock_trade(self, action: str, symbol: str, params: list, client_id: Optional[str] = None) -> str:
        """일반 주식 거래 처리"""
        try:
            # 파라미터 분석
            if not params:
                # 대화형 모드
                if client_id:
                    self.interactive_sessions[client_id] = {
                        'mode': 'stock_trade',
                        'action': action,
                        'symbol': symbol,
                        'step': 'amount'
                    }
                return self.config_manager.get_message('buy_amount_prompt' if action == 'BUY' else 'sell_amount_prompt', symbol=symbol)
            
            # 1개 파라미터: 수량/금액/비율
            elif len(params) == 1:
                amount_str = params[0]
                return await self._process_amount_input(action, symbol, amount_str, client_id)
            
            # 2개 파라미터: 수량 + 가격
            elif len(params) == 2:
                try:
                    qty = int(params[0])
                    price = float(params[1])
                    return await self._execute_limit_order(action, symbol, qty, price)
                except ValueError:
                    return self.config_manager.get_message('invalid_amount')
            
            return self.config_manager.get_message('invalid_format')
            
        except Exception as e:
            return self.config_manager.get_message('order_execution_failed', error=e)
    
    async def _handle_etf_buy(self, etf_name: str, params: list, client_id: Optional[str] = None) -> str:
        """ETF 매수 처리"""
        try:
            if not params:
                # ETF 대화형 모드
                if client_id:
                    self.interactive_sessions[client_id] = {
                        'mode': 'etf_buy',
                        'etf_name': etf_name,
                        'step': 'amount'
                    }
                return self.config_manager.get_message('etf_prompt', etf_name=etf_name)
            
            # ETF는 비율 또는 달러 금액만 허용
            amount_str = params[0]
            if amount_str.endswith('%') or amount_str.startswith('$'):
                return await self._execute_etf_purchase(etf_name, amount_str, client_id)
            else:
                return self.config_manager.get_message('etf_format_error')
                
        except Exception as e:
            return self.config_manager.get_message('etf_purchase_failed', error=e)
    
    async def _handle_sell_all(self, client_id: Optional[str] = None) -> str:
        """모든 포지션 매도 처리"""
        try:
            positions = await self.broker.get_positions()
            if not positions:
                return self.config_manager.get_message('no_positions')
            
            # 포지션 목록 표시
            position_text = "\\n".join([
                f"  {pos.get('symbol')}: {pos.get('qty')}주 (${pos.get('market_value', 0):.2f})"
                for pos in positions
            ])
            
            if client_id:
                self.interactive_sessions[client_id] = {
                    'mode': 'sell_all_confirm',
                    'positions': positions,
                    'step': 'confirm'
                }
            
            return self.config_manager.get_message('position_list', positions=position_text) + "\\n\\n전량 매도하시겠습니까? (Y/N):"
            
        except Exception as e:
            return self.config_manager.get_message('portfolio_failed', error=e)
    
    async def _process_amount_input(self, action: str, symbol: str, amount_str: str, client_id: Optional[str] = None) -> str:
        """수량/금액/비율 입력 처리"""
        try:
            # 비율 처리 (20% 형식)
            if amount_str.endswith('%'):
                percentage = float(amount_str[:-1])
                if client_id:
                    self.interactive_sessions[client_id] = {
                        'mode': 'price_input',
                        'action': action,
                        'symbol': symbol,
                        'amount_type': f"{percentage}%",
                        'percentage': percentage,
                        'step': 'price'
                    }
                return self.config_manager.get_message('buy_price_prompt' if action == 'BUY' else 'sell_price_prompt', 
                                                     symbol=symbol, amount_type=f"{percentage}%")
            
            # 달러 금액 처리 ($1000 형식)
            elif amount_str.startswith('$'):
                dollar_amount = float(amount_str[1:])
                if client_id:
                    self.interactive_sessions[client_id] = {
                        'mode': 'price_input',
                        'action': action,
                        'symbol': symbol,
                        'amount_type': f"${dollar_amount:.2f}",
                        'dollar_amount': dollar_amount,
                        'step': 'price'
                    }
                return self.config_manager.get_message('buy_price_prompt' if action == 'BUY' else 'sell_price_prompt',
                                                     symbol=symbol, amount_type=f"${dollar_amount:.2f}")
            
            # 일반 수량 처리
            else:
                qty = int(amount_str)
                if client_id:
                    self.interactive_sessions[client_id] = {
                        'mode': 'price_input',
                        'action': action,
                        'symbol': symbol,
                        'amount_type': f"{qty}주",
                        'qty': qty,
                        'step': 'price'
                    }
                return self.config_manager.get_message('buy_price_prompt' if action == 'BUY' else 'sell_price_prompt',
                                                     symbol=symbol, amount_type=f"{qty}주")
                                                     
        except (ValueError, IndexError):
            return self.config_manager.get_message('invalid_amount')
        except Exception as e:
            return self.config_manager.get_message('order_execution_failed', error=e)
    
    async def _execute_limit_order(self, action: str, symbol: str, qty: int, price: float) -> str:
        """지정가 주문 실행"""
        try:
            order_id = await self.broker.submit_order(
                symbol=symbol,
                qty=qty,
                side=action.lower(),
                order_type="limit",
                limit_price=price
            )
            
            return self.config_manager.get_message('order_complete', 
                                                 action=action, symbol=symbol, qty=qty, 
                                                 price=f"${price:.2f}", order_id=order_id)
        except Exception as e:
            return self.config_manager.get_message('order_execution_failed', error=e)
    
    async def _execute_etf_purchase(self, etf_name: str, amount_str: str, client_id: Optional[str] = None) -> str:
        """ETF 구매 실행"""
        try:
            import json
            with open('config/myETFs.json', 'r', encoding='utf-8') as f:
                etf_data = json.load(f)
            
            etf_config = etf_data['custom_etfs'][etf_name]
            
            # 총 투자 금액 계산
            if amount_str.endswith('%'):
                percentage = float(amount_str[:-1])
                account_info = await self.broker.get_account_info()
                buying_power = float(account_info.get('buying_power', 0))
                total_amount = buying_power * (percentage / 100)
            elif amount_str.startswith('$'):
                total_amount = float(amount_str[1:])
            else:
                return self.config_manager.get_message('etf_format_error')
            
            # ETF 구성에 따라 분배하여 매수
            breakdown_text = ""
            total_orders = 0
            
            for stock_symbol, weight in etf_config.items():
                stock_amount = total_amount * weight
                
                # 현재 가격 조회
                quote = await self.broker.get_quote(stock_symbol)
                if not quote:
                    continue
                
                current_price = (quote.get('bid', 0) + quote.get('ask', 0)) / 2
                if current_price <= 0:
                    continue
                
                qty = int(stock_amount / current_price)
                if qty > 0:
                    order_id = await self.broker.submit_order(
                        symbol=stock_symbol,
                        qty=qty,
                        side="buy",
                        order_type="market"
                    )
                    breakdown_text += f"  {stock_symbol}: {qty}주 (${stock_amount:.2f})\\n"
                    total_orders += 1
            
            return (self.config_manager.get_message('etf_breakdown', etf_name=etf_name, breakdown=breakdown_text) +
                   f"\\n✅ {total_orders}개 종목 주문 완료 (총 ${total_amount:.2f})")
            
        except Exception as e:
            return self.config_manager.get_message('etf_purchase_failed', error=e)
    
    async def _execute_percentage_trade(self, action: str, symbol: str, percentage: float) -> str:
        """비율 기반 거래 실행"""
        try:
            account_info = await self.broker.get_account_info()
            buying_power = float(account_info.get('buying_power', 0))
            
            target_amount = buying_power * (percentage / 100)
            
            # 현재 가격 조회
            quote = await self.broker.get_quote(symbol)
            if not quote:
                return self.config_manager.get_message('quote_fetch_failed', symbol=symbol)
            
            current_price = (float(quote.get('ask', 0)) + float(quote.get('bid', 0))) / 2
            if current_price <= 0:
                return self.config_manager.get_message('invalid_price', symbol=symbol, price=current_price)
            
            qty = int(target_amount / current_price)
            if qty <= 0:
                return self.config_manager.get_message('insufficient_budget', budget=target_amount, price=current_price)
            
            # 주문 실행
            order_id = await self.broker.submit_order(
                symbol=symbol,
                qty=qty,
                side=action.lower(),
                order_type="market"
            )
            
            actual_amount = qty * current_price
            return self.config_manager.get_message('percentage_order_success', percentage=percentage, action=action, symbol=symbol, qty=qty, amount=actual_amount, order_id=order_id)
            
        except Exception as e:
            return self.config_manager.get_message('percentage_trade_failed', error=str(e))
    
    async def _parse_etf_command(self, command: str, client_id: Optional[str] = None) -> str:
        """ETF 명령어 파싱"""
        try:
            parts = command.strip().split()
            etf_name = parts[1].upper()
            
            if len(parts) == 2:
                # ETF 대화형 모드
                if client_id:
                    self.interactive_sessions[client_id] = {
                        'mode': 'etf_buy',
                        'etf_name': etf_name,
                        'step': 'amount'
                    }
                return self.config_manager.get_message('etf_buy_prompt', etf_name=etf_name)
            
            # 비율 기반 ETF 구매
            if len(parts) == 3 and parts[2].endswith('%'):
                percentage = float(parts[2][:-1])
                return await self._execute_etf_purchase(etf_name, percentage=percentage)
                
            return self.config_manager.get_message('etf_command_format_error')
            
        except Exception as e:
            return self.config_manager.get_message('etf_command_failed', error=str(e))
    
    async def _execute_etf_purchase(self, etf_name: str, percentage: float = None, amount: float = None) -> str:
        """ETF 구매 실행"""
        try:
            # ETF 구성 정보 로드
            import json
            with open('config/myETFs.json', 'r', encoding='utf-8') as f:
                etf_data = json.load(f)
            
            etf_config = etf_data['custom_etfs'].get(etf_name)
            if not etf_config:
                return self.config_manager.get_message('etf_not_found', etf_name=etf_name)
            
            # 투자 금액 계산
            if percentage:
                account_info = await self.broker.get_account_info()
                buying_power = float(account_info.get('buying_power', 0))
                total_amount = buying_power * (percentage / 100)
            elif amount:
                total_amount = amount
            else:
                return "❌ 투자 금액 또는 비율을 지정해야 합니다."
            
            # 각 구성 종목별 주문 실행
            results = []
            components = etf_config['components']
            
            for component in components:
                symbol = component['symbol']
                weight = component['weight'] / 100
                component_amount = total_amount * weight
                
                # 현재 가격 조회
                quote = await self.broker.get_quote(symbol)
                if quote:
                    current_price = (float(quote.get('ask', 0)) + float(quote.get('bid', 0))) / 2
                    if current_price > 0:
                        qty = int(component_amount / current_price)
                        if qty > 0:
                            order_id = await self.broker.submit_order(
                                symbol=symbol,
                                qty=qty,
                                side="buy",
                                order_type="market"
                            )
                            results.append(f"  {symbol}: {qty}주 (${component_amount:.2f})")
                        else:
                            results.append(f"  {symbol}: 수량 부족")
                    else:
                        results.append(f"  {symbol}: 가격 조회 실패")
                else:
                    results.append(f"  {symbol}: 시세 조회 실패")
            
            result_text = f"✅ {etf_name} ETF 구매 완료 (총 ${total_amount:.2f})\\n"
            result_text += "\\n".join(results)
            return result_text
            
        except Exception as e:
            return self.config_manager.get_message('etf_purchase_failed', error=str(e))

    async def _handle_interactive(self, client_id: str, command: str) -> str:
        """대화형 모드 처리"""
        try:
            if not client_id or client_id not in self.interactive_sessions:
                logger.error(f"Invalid session: client_id={client_id}")
                return self.config_manager.get_message("session_expired")
                
            session = self.interactive_sessions.get(client_id, {})
            mode = session.get('mode')
            step = session.get('step')
            
            logger.info(f"Interactive mode: {mode}, step: {step}, client: {client_id}")
            
            if mode == 'quick_buy':
                symbol = session['symbol']
                return await self._handle_quick_buy_input(client_id, symbol, command)
                
            elif mode == 'trade':
                action = session['action']
                symbol = session['symbol']
                return await self._handle_trade_input(client_id, action, symbol, command)
                
            elif mode == 'etf_buy':
                etf_name = session['etf_name']
                return await self._handle_etf_input(client_id, etf_name, command)
            
            elif mode == 'buy_symbol':
                return await self._handle_buy_symbol_input(client_id, command)
            
            elif mode == 'auto_start_confirm':
                return await self._handle_auto_start_confirm(client_id, command)
            
            elif mode == 'auto_stop_confirm':
                return await self._handle_auto_stop_confirm(client_id, command)
            
            elif mode == 'price_input':
                return await self._handle_price_input(client_id, command)
            
            elif mode == 'confirmation':
                return await self._handle_trade_confirmation(client_id, command)
            
            # 세션 정리
            del self.interactive_sessions[client_id]
            return self.config_manager.get_message('unknown_interactive_mode')
            
        except Exception as e:
            # 세션 정리
            if client_id in self.interactive_sessions:
                del self.interactive_sessions[client_id]
            logger.error(f"대화형 처리 오류 (client_id: {client_id}): {e}")
            return self.config_manager.get_message('interactive_processing_error', error=str(e))
    
    async def _handle_auto_start_confirm(self, client_id: str, command: str) -> str:
        """자동매매 시작 확인 처리"""
        try:
            session = self.interactive_sessions.get(client_id, {})
            auto_config = session.get('auto_config')
            
            # 세션 정리
            del self.interactive_sessions[client_id]
            
            if command.upper() in ['Y', 'YES', 'ㅇ', '예']:
                # 자동매매 시작
                await self.strategy_runner.start_auto_trading()
                return self.config_manager.get_message('auto_trading_started')
            else:
                # 취소
                return self.config_manager.get_message('auto_start_cancelled')
                
        except Exception as e:
            if client_id in self.interactive_sessions:
                del self.interactive_sessions[client_id]
            return self.config_manager.get_message('auto_start_failed', error=str(e))
    
    async def _handle_auto_stop_confirm(self, client_id: str, command: str) -> str:
        """자동매매 중지 확인 처리"""
        try:
            session = self.interactive_sessions.get(client_id, {})
            current_status = session.get('current_status')
            
            # 세션 정리
            del self.interactive_sessions[client_id]
            
            if command.upper() in ['Y', 'YES', 'ㅇ', '예']:
                # 자동매매 중지
                await self.strategy_runner.stop_auto_trading()
                return self.config_manager.get_message('auto_trading_stopped')
            else:
                # 취소
                return self.config_manager.get_message('auto_stop_cancelled')
                
        except Exception as e:
            if client_id in self.interactive_sessions:
                del self.interactive_sessions[client_id]
            return self.config_manager.get_message('auto_stop_failed', error=str(e))
    
    async def _handle_price_input(self, client_id: str, command: str) -> str:
        """가격 입력 처리"""
        try:
            session = self.interactive_sessions.get(client_id, {})
            symbol = session['symbol']
            qty = session['qty']
            
            if command.strip() == '' or command.strip().lower() == 'market':
                # 시장가 주문
                order_type = self.config_manager.get_message('market_price')
                
                # 시세 조회하여 예상 금액 계산
                quote = await self.broker.get_quote(symbol)
                if quote:
                    current_price = (float(quote.get('ask', 0)) + float(quote.get('bid', 0))) / 2
                    estimated_amount = current_price * qty
                else:
                    estimated_amount = 0
                
                # 최종 확인 단계로 전환
                self.interactive_sessions[client_id] = {
                    'mode': 'confirmation',
                    'symbol': symbol,
                    'qty': qty,
                    'order_type': 'market',
                    'price': None,
                    'amount': estimated_amount
                }
                
                return self.config_manager.get_message('confirmation_prompt', 
                    symbol=symbol, qty=qty, order_type=order_type, amount=estimated_amount)
            else:
                # 지정가 주문
                try:
                    price = float(command)
                    order_type = f"${price:.2f}"
                    estimated_amount = price * qty
                    
                    # 최종 확인 단계로 전환
                    self.interactive_sessions[client_id] = {
                        'mode': 'confirmation',
                        'symbol': symbol,
                        'qty': qty,
                        'order_type': 'limit',
                        'price': price,
                        'amount': estimated_amount
                    }
                    
                    return self.config_manager.get_message('confirmation_prompt', 
                        symbol=symbol, qty=qty, order_type=order_type, amount=estimated_amount)
                        
                except ValueError:
                    # 세션 정리
                    del self.interactive_sessions[client_id]
                    return self.config_manager.get_message("invalid_price_format")
                    
        except Exception as e:
            if client_id in self.interactive_sessions:
                del self.interactive_sessions[client_id]
            return self.config_manager.get_message("price_input_error", error=str(e))
    
    async def _handle_trade_confirmation(self, client_id: str, command: str) -> str:
        """거래 최종 확인 처리"""
        try:
            session = self.interactive_sessions.get(client_id, {})
            symbol = session['symbol']
            qty = session['qty']
            order_type = session['order_type']
            price = session.get('price')
            
            # 세션 정리
            del self.interactive_sessions[client_id]
            
            if command.upper() in ['Y', 'YES', 'ㅇ', '예']:
                # 주문 실행
                if order_type == 'market':
                    order_id = await self.broker.submit_order(
                        symbol=symbol,
                        qty=qty,
                        side="buy",
                        order_type="market"
                    )
                    order_type_text = self.config_manager.get_message('market_price')
                else:
                    order_id = await self.broker.submit_order(
                        symbol=symbol,
                        qty=qty,
                        side="buy",
                        order_type="limit",
                        limit_price=price
                    )
                    order_type_text = f"${price:.2f}"
                
                return self.config_manager.get_message('order_confirmation_success', 
                    symbol=symbol, qty=qty, order_type=order_type_text, order_id=order_id)
            else:
                # 주문 취소
                return self.config_manager.get_message('order_confirmation_cancelled')
                
        except Exception as e:
            if client_id in self.interactive_sessions:
                del self.interactive_sessions[client_id]
            return self.config_manager.get_message('order_processing_error', error=str(e))
    
    async def _handle_quick_buy_input(self, client_id: str, symbol: str, command: str) -> str:
        """간편 매수 입력 처리"""
        try:
            if command.endswith('%'):
                # 비율 기반 - 즉시 실행
                del self.interactive_sessions[client_id]
                percentage = float(command[:-1])
                return await self._execute_percentage_trade('BUY', symbol, percentage)
            elif command.startswith('$'):
                # 금액 기반 - 즉시 실행
                del self.interactive_sessions[client_id]
                amount = float(command[1:])
                quote = await self.broker.get_quote(symbol)
                if quote:
                    current_price = (float(quote.get('ask', 0)) + float(quote.get('bid', 0))) / 2
                    if current_price > 0:
                        qty = int(amount / current_price)
                        order_id = await self.broker.submit_order(
                            symbol=symbol,
                            qty=qty,
                            side="buy",
                            order_type="market"
                        )
                        return self.config_manager.get_message('quick_buy_success', symbol=symbol, amount=amount, qty=qty, order_id=order_id)
                return self.config_manager.get_message('quote_fetch_failed', symbol=symbol)
            else:
                # 수량 기반 ("50주" 또는 "50" 형식) - 가격 입력 단계로
                amount_str = command.strip()
                if amount_str.endswith('주'):
                    amount_str = amount_str[:-1]  # "주" 제거
                
                qty = int(float(amount_str))
                # 가격 입력 단계로 전환 (세션 유지)
                self.interactive_sessions[client_id] = {
                    'mode': 'price_input',
                    'symbol': symbol,
                    'qty': qty,
                    'step': 'price'
                }
                return self.config_manager.get_message('buy_price_prompt', symbol=symbol, amount_type=f"{qty}주")
                    
        except ValueError:
            del self.interactive_sessions[client_id]
            return self.config_manager.get_message('invalid_input_format')
        except Exception as e:
            del self.interactive_sessions[client_id]
            return self.config_manager.get_message('buy_processing_failed', error=str(e))
    
    async def _handle_buy_symbol_input(self, client_id: str, command: str) -> str:
        """BUY 명령어 후 종목명 입력 처리"""
        try:
            cmd_upper = command.upper().strip()
            
            # .TICKER 형태 확인
            if command.startswith('.') and len(command.split()) == 1:
                symbol = command[1:].upper()
                # 간편 매수 모드로 전환
                self.interactive_sessions[client_id] = {
                    'mode': 'quick_buy',
                    'symbol': symbol,
                    'step': 'amount'
                }
                return self.config_manager.get_message('quick_buy_prompt', symbol=symbol)
            
            # ETF 확인
            etfs = self.config_manager.get_etfs()
            if cmd_upper in etfs:
                # ETF 매수 모드로 전환
                self.interactive_sessions[client_id] = {
                    'mode': 'etf_buy',
                    'etf_name': cmd_upper
                }
                return self.config_manager.get_message('etf_prompt', {'etf_name': cmd_upper})
            
            # 일반 종목명이면 안내
            if command.isalpha() and len(command) >= 2:
                del self.interactive_sessions[client_id]
                return self.config_manager.get_message('unknown_symbol_hint', command=command.upper())
            
            # 잘못된 입력
            del self.interactive_sessions[client_id]
            return self.config_manager.get_message('invalid_symbol_input')
            
        except Exception as e:
            if client_id in self.interactive_sessions:
                del self.interactive_sessions[client_id]
            return self.config_manager.get_message('input_processing_error', error=str(e))
    
    async def _handle_trade_input(self, client_id: str, action: str, symbol: str, command: str) -> str:
        """거래 입력 처리"""
        # quick_buy와 동일한 로직 사용
        return await self._handle_quick_buy_input(client_id, symbol, command)
    

    async def _handle_etf_input(self, client_id: str, etf_name: str, command: str) -> str:
        """ETF 입력 처리"""
        try:
            del self.interactive_sessions[client_id]
            
            if command.endswith('%'):
                percentage = float(command[:-1])
                return await self._execute_etf_purchase(etf_name, percentage=percentage)
            elif command.startswith('$'):
                amount = float(command[1:])
                return await self._execute_etf_purchase(etf_name, amount=amount)
            else:
                return self.config_manager.get_message("errors.etf_command_format_error")
                
        except ValueError:
            return self.config_manager.get_message('errors.invalid_input_format')
        except Exception as e:
            del self.interactive_sessions[client_id]
            return self.config_manager.get_message('errors.etf_command_failed', error=str(e))
