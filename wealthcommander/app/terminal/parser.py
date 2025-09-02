# app/terminal/parser.py
# (이 파일은 해당 시점에 변경되지 않았으므로 이전 코드를 그대로 사용합니다.)
from typing import Dict
import re

# ... (기존 parser.py 코드)
def parse(line: str) -> Dict:
    s = line.strip()
    parts = s.split()
    cmd = parts[0].upper() if parts else ""

    raw = {"raw": line}

    if not cmd:
        return {}

    # Simple commands
    if cmd in ["HELP", "STATUS", "PORTFOLIO", "POSITIONS", "BALANCE", "ORDERS", "HISTORY", "CLEAR"]:
        return {"cmd": cmd}

    # .TICKER
    if cmd.startswith('.') and len(cmd) > 1:
        return {"cmd": "INFO", "symbol": cmd[1:].upper()}

    # AUTO ON/OFF
    if cmd == "AUTO" and len(parts) == 2 and parts[1].upper() in ["ON", "OFF"]:
        return {"cmd": "AUTO", "enabled": parts[1].upper() == "ON"}

    # STRATEGY {name}
    if cmd == "STRATEGY" and len(parts) > 1:
        return {"cmd": "STRATEGY", "name": " ".join(parts[1:])}

    # INTERVAL {seconds}
    if cmd == "INTERVAL" and len(parts) == 2 and parts[1].isdigit():
        return {"cmd": "INTERVAL", "seconds": int(parts[1])}

    # CANCEL {order_id}
    if cmd == "CANCEL" and len(parts) == 2:
        return {"cmd": "CANCEL", "order_id": parts[1]}

    # BUY/SELL
    if cmd in ["BUY", "SELL"]:
        if len(parts) == 1:
             return {"cmd": cmd, "target": "INTERACTIVE"}
        if len(parts) >= 2 and parts[1].startswith('.'):
            res = {"cmd": cmd, "target": "TICKER", "symbol": parts[1][1:].upper()}
            if len(parts) > 2:
                qty_str = parts[2]
                if qty_str.endswith('%'):
                    res["bp_pct"] = float(qty_str[:-1])
                elif qty_str.startswith('$'):
                    res["budget_usd"] = float(qty_str[1:])
                else:
                    res["qty"] = float(qty_str)

            if len(parts) > 3:
                res["limit_price"] = float(parts[3])
            return res

    return raw