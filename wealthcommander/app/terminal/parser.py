# app/terminal/parser.py
import re
from typing import Dict, Any

# 정규식 패턴
NUMBER = r"(?P<num>\d+(\.\d+)?)"
PRICE = r"(?P<price>\d+(\.\d+)?)"
PCT = r"(?P<pct>\d+(\.\d+)?)%"
USD = r"\$(?P<usd>\d+(\.\d+)?)"
TICK = r"\.(?P<ticker>[A-Za-z\.]{1,10})"
ETFKEY = r"(?P<etfkey>[A-Za-z0-9_\-]{1,50})"

def parse(cmd: str) -> Dict[str, Any]:
    """명령어 파싱"""
    s = cmd.strip()
    up = s.upper()
    
    # 기본 명령어
    simple_commands = {
        "HELP": {"cmd": "HELP"},
        "STATUS": {"cmd": "STATUS"},
        "PORTFOLIO": {"cmd": "PORTFOLIO"},
        "ORDERS": {"cmd": "ORDERS"},
        "HISTORY": {"cmd": "HISTORY"},
        "POSITIONS": {"cmd": "POSITIONS"},
        "BALANCE": {"cmd": "BALANCE"},
        "CLEAR": {"cmd": "CLEAR"}
    }
    
    if up in simple_commands:
        return simple_commands[up]
    
    # MODE 명령어
    if up.startswith("MODE "):
        m = re.match(r"MODE\s+(PAPER|LIVE)$", up)
        if m:
            return {"cmd": "MODE", "mode": m.group(1)}
    
    # AUTO 명령어
    if up.startswith("AUTO "):
        m = re.match(r"AUTO\s+(ON|OFF)$", up)
        if m:
            return {"cmd": "AUTO", "enabled": (m.group(1) == "ON")}
    
    # 전략 명령어
    if up.startswith("STRATEGY "):
        strategy_name = s[9:].strip()
        return {"cmd": "STRATEGY", "name": strategy_name}
    
    # 티커 정보 조회
    if re.fullmatch(TICK, s):
        m = re.fullmatch(TICK, s)
        return {"cmd": "INFO", "symbol": m.group("ticker").upper()}
    
    # 매수/매도 명령어
    action = None
    if up.startswith("BUY"):
        action = "BUY"
    elif up.startswith("SELL"):
        action = "SELL"
    
    if action:
        rest = s[len(action):].strip()
        
        # 빈 명령어 -> 대화형 모드
        if not rest:
            return {"cmd": action, "target": "INTERACTIVE"}
        
        # 개별 종목 매매
        if rest.startswith("."):
            # 패턴: .TICKER [수량/비율/금액] [지정가]
            pattern = rf"^{TICK}(?:\s+({NUMBER}|{PCT}|{USD}))?(?:\s+{PRICE})?$"
            m = re.match(pattern, rest)
            
            if m:
                result = {
                    "cmd": action,
                    "target": "TICKER",
                    "symbol": m.group("ticker").upper()
                }
                
                # 수량/비율/금액 파싱
                if m.group("num"):
                    result["qty"] = float(m.group("num"))
                elif m.group("pct"):
                    result["bp_pct"] = float(m.group("pct"))
                elif m.group("usd"):
                    result["budget_usd"] = float(m.group("usd"))
                
                # 지정가 파싱
                if m.group("price"):
                    result["limit_price"] = float(m.group("price"))
                
                return result
        
        # myETF 매매
        m = re.match(rf"^{ETFKEY}\s+({USD}|{PCT})$", rest)
        if m:
            return {
                "cmd": action,
                "target": "MYETF",
                "key": m.group("etfkey"),
                "budget_usd": float(m.group("usd")) if m.group("usd") else None,
                "bp_pct": float(m.group("pct")) if m.group("pct") else None
            }
    
    # CANCEL 명령어
    if up.startswith("CANCEL "):
        order_id = s[7:].strip()
        return {"cmd": "CANCEL", "order_id": order_id}
    
    # INTERVAL 명령어
    if up.startswith("INTERVAL "):
        m = re.match(r"INTERVAL\s+(\d+)$", up)
        if m:
            return {"cmd": "INTERVAL", "seconds": int(m.group(1))}
    
    # 알 수 없는 명령어
    return {"cmd": "UNKNOWN", "raw": s}