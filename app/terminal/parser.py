# app/terminal/parser.py
import re
from typing import Dict, Any

# --- 명령어 파싱을 위한 정규 표현식 패턴 ---
NUMBER = r"(?P<num>\d+(\.\d+)?)"
PRICE  = r"(?P<price>\d+(\.\d+)?)"
PCT    = r"(?P<pct>\d+(\.\d+)?)%"
USD    = r"\$(?P<usd>\d+(\.\d+)?)"
TICK   = r"\.(?P<ticker>[A-Za-z\.]{1,10})"
ETFKEY = r"(?P<etfkey>[A-Za-z0-9_\-]{1,50})"

def parse(cmd: str) -> Dict[str, Any]:
    """사용자가 입력한 문자열 명령어를 파싱하여 딕셔너리 형태로 변환합니다."""
    s = cmd.strip()
    up = s.upper()

    # --- 간단한 명령어 처리 ---
    if up == "HELP": return {"cmd": "HELP"}
    if up == "STATUS": return {"cmd": "STATUS"}
    if up == "PORTFOLIO": return {"cmd": "PORTFOLIO"}
    if up == "ORDERS": return {"cmd": "ORDERS"}
    if up == "HISTORY": return {"cmd": "HISTORY"}
    
    # --- 인자가 있는 명령어 처리 ---
    if up.startswith("MODE "):
        m = re.match(r"MODE\s+(PAPER|LIVE)$", up)
        if m: return {"cmd": "MODE", "mode": m.group(1)}
    if up.startswith("AUTO "):
        m = re.match(r"AUTO\s+(ON|OFF)$", up)
        if m: return {"cmd": "AUTO", "enabled": (m.group(1) == "ON")}
    if up.startswith("LOGS "):
        return {"cmd": "LOGS", "date": s.split(" ", 1)[1].strip()}

    # --- 심볼 정보 조회 명령어 (.AAPL 등) ---
    if re.fullmatch(TICK, s):
        m = re.fullmatch(TICK, s)
        return {"cmd": "INFO", "symbol": m.group("ticker").upper()}

    # --- 매수/매도 명령어 처리 ---
    action = "BUY" if up.startswith("BUY") else ("SELL" if up.startswith("SELL") else None)
    if action:
        rest = s[len(action):].strip()
        
        # 개별 종목 매매 (예: BUY .AAPL 10)
        if rest.startswith("."):
            m = re.match(rf"^{TICK}(?:\s+({NUMBER}|{PCT}|{USD}))?(?:\s+{PRICE})?$", rest)
            if m:
                qty_token = m.group("num")
                pct_token = m.group("pct")
                usd_token = m.group("usd")
                price     = m.group("price")
                return {
                    "cmd": action, "target": "TICKER", "symbol": m.group("ticker").upper(),
                    "qty": float(qty_token) if qty_token else None,
                    "bp_pct": float(pct_token) if pct_token else None,
                    "budget_usd": float(usd_token) if usd_token else None,
                    "limit_price": float(price) if price else None
                }
        
        # myETF 매매 (예: BUY myETF1 $1000)
        m = re.match(rf"^{ETFKEY}\s+({USD}|{PCT})$", rest)
        if m:
            return {
                "cmd": action, "target": "MYETF", "key": m.group("etfkey"),
                "budget_usd": float(m.group("usd")) if m.group("usd") else None,
                "bp_pct": float(m.group("pct")) if m.group("pct") else None
            }
            
        # 대화형 매매 시작 (예: BUY)
        if rest == "":
            return {"cmd": action, "target": "INTERACTIVE"}

    # --- 주문 취소 명령어 ---
    if up.startswith("CANCEL "):
        return {"cmd": "CANCEL", "order_id": s.split(" ", 1)[1].strip()}

    # --- 일치하는 명령어가 없는 경우 ---
    return {"cmd": "UNKNOWN", "raw": s}