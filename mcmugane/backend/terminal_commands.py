import re
from typing import Dict, Any, Optional
from alpaca_client import AlpacaClient
import json
from datetime import datetime
import pytz

class TerminalCommands:
    def __init__(self, alpaca_client: AlpacaClient, config_manager):
        self.alpaca = alpaca_client
        self.config = config_manager
        self.mode = "PAPER"
        self.auto_trading = False
        
        # 설정에서 타임존과 포맷 로드
        self.user_config = self.load_user_config()
        self.timezone = pytz.timezone(self.user_config.get('timezone', 'America/New_York'))
        self.date_format = self.get_date_format()
        
    def load_user_config(self):
        """사용자 설정 로드"""
        with open('/app/config/user-defined.json', 'r') as f:
            return json.load(f)
    
    def get_date_format(self):
        """현재 설정된 날짜 포맷 가져오기"""
        format_mode = self.user_config['display']['currentDateFormat']
        formats = self.user_config['display']['dateFormat']
        return formats.get(format_mode, formats['us'])
    
    def format_datetime(self, dt: datetime) -> str:
        """날짜시간을 사용자 설정에 맞게 포맷"""
        localized_dt = dt.astimezone(self.timezone)
        
        # Python datetime format으로 변환
        format_str = self.date_format.replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d')
        format_str = format_str.replace('h', '%I').replace('HH', '%H').replace('mm', '%M').replace('ss', '%S')
        format_str = format_str.replace('A', '%p')
        
        return localized_dt.strftime(format_str)
    
    def get_market_status(self) -> Dict[str, Any]:
        """현재 시장 상태 확인"""
        now = datetime.now(self.timezone)
        current_time = now.time()
        
        market_hours = self.user_config['market']['tradingHours']
        
        # 휴장일 체크
        today_str = now.strftime('%Y-%m-%d')
        if today_str in self.user_config['market']['holidays']:
            return {
                'status': 'CLOSED',
                'reason': 'Market Holiday',
                'next_open': self.get_next_market_open()
            }
        
        # 주말 체크
        if now.weekday() >= 5:  # 토요일(5), 일요일(6)
            return {
                'status': 'CLOSED',
                'reason': 'Weekend',
                'next_open': self.get_next_market_open()
            }
        
        # 시간대별 상태 체크
        pre_start = datetime.strptime(market_hours['preMarket']['start'], '%H:%M').time()
        pre_end = datetime.strptime(market_hours['preMarket']['end'], '%H:%M').time()
        regular_start = datetime.strptime(market_hours['regular']['start'], '%H:%M').time()
        regular_end = datetime.strptime(market_hours['regular']['end'], '%H:%M').time()
        after_start = datetime.strptime(market_hours['afterHours']['start'], '%H:%M').time()
        after_end = datetime.strptime(market_hours['afterHours']['end'], '%H:%M').time()
        
        if pre_start <= current_time < pre_end:
            return {'status': 'PRE_MARKET', 'session': 'Pre-Market'}
        elif regular_start <= current_time < regular_end:
            return {'status': 'OPEN', 'session': 'Regular Trading'}
        elif after_start <= current_time < after_end:
            return {'status': 'AFTER_HOURS', 'session': 'After-Hours'}
        else:
            return {'status': 'CLOSED', 'reason': 'Outside Trading Hours'}
    
    def show_status(self, args: list) -> Dict[str, Any]:
        """상태 표시 - 시장 상태 포함"""
        account = self.alpaca.get_account()
        market_status = self.get_market_status()
        
        # 색상 모드 가져오기
        color_mode = self.user_config['display']['currentColorMode']
        colors = self.user_config['display']['colorScheme'][color_mode]
        
        status_text = f"""
╔══════════════════════════════════════════════════════╗
║                   SYSTEM STATUS                       ║
╠══════════════════════════════════════════════════════╣
║ Mode:           {self.mode:38} ║
║ Auto Trading:   {'ON' if self.auto_trading else 'OFF':38} ║
║ Market Status:  {market_status['status']:38} ║
║ Session:        {market_status.get('session', 'Closed'):38} ║
║ Current Time:   {self.format_datetime(datetime.now()):38} ║
╠══════════════════════════════════════════════════════╣
║                  ACCOUNT STATUS                       ║
╠══════════════════════════════════════════════════════╣
║ Buying Power:   ${float(account['buying_power']):37,.2f} ║
║ Portfolio Val:  ${float(account['portfolio_value']):37,.2f} ║
║ Cash:           ${float(account['cash']):37,.2f} ║
║ Day Trades:     {account['day_trade_count']:38} ║
║ Color Scheme:   {color_mode.upper():38} ║
║ Timezone:       {str(self.timezone):38} ║
╚══════════════════════════════════════════════════════╝
        """
        return {"success": True, "message": status_text}
    
    def switch_locale(self, locale: str) -> Dict[str, Any]:
        """언어/지역 설정 전환"""
        valid_locales = ['us', 'ko']
        
        if locale.lower() not in valid_locales:
            return {"error": f"Invalid locale. Use: {', '.join(valid_locales)}"}
        
        # 설정 업데이트
        self.user_config['display']['currentColorMode'] = locale.lower()
        self.user_config['display']['currentDateFormat'] = locale.lower()
        
        if locale.lower() == 'ko':
            self.user_config['timezone'] = 'Asia/Seoul'
            self.user_config['regional']['preferredLanguage'] = 'ko'
        else:
            self.user_config['timezone'] = 'America/New_York'
            self.user_config['regional']['preferredLanguage'] = 'en-US'
        
        # 설정 저장
        with open('/app/config/user-defined.json', 'w') as f:
            json.dump(self.user_config, f, indent=2)
        
        # 현재 인스턴스 업데이트
        self.timezone = pytz.timezone(self.user_config['timezone'])
        self.date_format = self.get_date_format()
        
        return {"success": True, "message": f"Switched to {locale.upper()} locale"}
    
    def show_logs(self, args: list) -> Dict[str, Any]:
        """로그 표시 - 날짜 포맷 적용"""
        if len(args) == 0:
            # 오늘 날짜 사용
            target_date = datetime.now(self.timezone).strftime('%Y%m%d')
        else:
            # 입력된 날짜 파싱 (다양한 포맷 지원)
            date_str = args[0]
            try:
                # YYYYMMDD 형식
                if len(date_str) == 8 and date_str.isdigit():
                    target_date = date_str
                # YYYY-MM-DD 형식
                elif '-' in date_str:
                    target_date = date_str.replace('-', '')
                # MM/DD/YYYY 형식
                elif '/' in date_str:
                    parts = date_str.split('/')
                    if len(parts) == 3:
                        if len(parts[2]) == 4:  # MM/DD/YYYY
                            target_date = f"{parts[2]}{parts[0].zfill(2)}{parts[1].zfill(2)}"
                        else:  # MM/DD/YY
                            year = f"20{parts[2]}"
                            target_date = f"{year}{parts[0].zfill(2)}{parts[1].zfill(2)}"
                else:
                    return {"error": "Invalid date format. Use: YYYYMMDD, YYYY-MM-DD, or MM/DD/YYYY"}
            except:
                return {"error": "Error parsing date"}
        
        # 로그 파일 읽기
        log_file = f'/app/logs/{target_date}.log'
        try:
            with open(log_file, 'r') as f:
                logs = f.readlines()
                
            formatted_logs = []
            for log in logs[-50:]:  # 최근 50개만
                log_entry = json.loads(log)
                timestamp = datetime.fromisoformat(log_entry['timestamp'])
                formatted_time = self.format_datetime(timestamp)
                formatted_logs.append(f"[{formatted_time}] {log_entry.get('command', '')} -> {log_entry.get('result', '')}")
            
            return {"success": True, "message": '\n'.join(formatted_logs)}
        except FileNotFoundError:
            return {"error": f"No logs found for {target_date}"}
        except Exception as e:
            return {"error": f"Error reading logs: {str(e)}"}