# api.py
# 외부 서비스(Stooq, Alpaca)와의 모든 통신(API 호출)을 담당하는 파일입니다.
# 각 API 호출 함수는 데이터를 가져와 프로그램이 사용하기 좋은 형태로 가공하여 반환합니다.

import requests, json, csv, io
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
from core import ET_TZ

# --- 세션 및 기본 설정 ---
_session = requests.Session()
_session.headers.update({"User-Agent":"WealthCommander/3.5"}) # 프로그램 식별을 위한 User-Agent
_session.timeout = 20  # API 응답이 20초 이상 없으면 타임아웃 처리

# --- 설정 파일 로더 ---
def _alp_conf():
    """설정 파일(userdefined.json)에서 Alpaca API 관련 설정을 읽어옵니다."""
    from config import get_config, get_mode, get_feed
    cfg=get_config(); alp=cfg.get("alpaca",{}); mode=get_mode().lower()
    base=alp.get(mode,{}).get("base"); key=alp.get(mode,{}).get("key"); sec=alp.get(mode,{}).get("secret")
    market=alp.get("market","https://data.alpaca.markets"); feed=get_feed()
    return {"BASE":base,"KEY":key,"SEC":sec,"MKT":market,"FEED":feed}

def _alp_headers():
    """Alpaca API 요청에 필요한 인증 헤더를 생성합니다."""
    c=_alp_conf()
    return {"APCA-API-KEY-ID": c["KEY"] or "", "APCA-API-SECRET-KEY": c["SEC"] or ""}

# --- 핵심 HTTP 요청 함수 ---
def _http_json(method, url, **kw):
    """모든 API 요청의 기반이 되는 함수. 요청 실패 시 예외 처리를 담당합니다."""
    params=kw.pop("params",{}) or {}
    # Alpaca 데이터 API 요청 시, 설정된 feed(iex/sip)를 자동으로 추가
    if url.startswith("https://data.alpaca.markets") and "feed" not in params:
        params["feed"]=_alp_conf()["FEED"]
    try:
        r=_session.request(method, url, headers={**_alp_headers(), **kw.pop("headers",{})}, params=params, timeout=20, **kw)
        js=r.json()
        if not r.ok: # 요청이 실패했다면(200 OK가 아니라면)
            message = js.get("message") or js.get("error", f"HTTP {r.status_code} 에러")
            raise RuntimeError(f"Alpaca API 에러: {message}")
        return js
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"네트워크 연결 오류: {e}")
    except json.JSONDecodeError:
        raise RuntimeError("API 응답을 파싱할 수 없습니다 (JSON 형식 오류).")

# --- Stooq API 함수 ---
def stooq_light(sym):
    """Stooq에서 특정 종목의 최신 시세(OHLC, 거래량)를 가져옵니다. .TICKER 명령어에서 사용됩니다."""
    try:
        url=f"https://stooq.com/q/l/?s={sym.lower()}.us&f=sd2t2ohlcv&h&e=csv"
        r=_session.get(url,timeout=15); r.raise_for_status()
        rd=list(csv.DictReader(io.StringIO(r.text)))
        if not rd: return None
        d=rd[0]
        return {"Date":d.get("Date"),"Time":d.get("Time"), "Open":float(d.get("Open") or "nan"),"High":float(d.get("High") or "nan"), "Low":float(d.get("Low") or "nan"),"Close":float(d.get("Close") or "nan"), "Volume":int(float(d.get("Volume") or 0))}
    except Exception:
        return None

def stooq_daily(sym, days=4000):
    """Stooq에서 특정 종목의 일봉 데이터를 지정된 기간만큼 가져옵니다. chart 명령어에서 사용됩니다."""
    try:
        url=f"https://stooq.com/q/d/l/?s={sym.lower()}.us&i=d"
        r=_session.get(url,timeout=15); r.raise_for_status()
        out=[]
        for row in csv.DictReader(io.StringIO(r.text)):
            try: out.append({"t":row["Date"],"o":float(row["Open"]),"h":float(row["High"]),"l":float(row["Low"]),"c":float(row["Close"]),"v":int(float(row["Volume"] or 0))})
            except: pass
        return out[-days:]
    except Exception:
        return []

# --- Alpaca API 함수 ---
def alp_acct():
    """Alpaca 계좌 정보를 가져옵니다."""
    try: return _http_json("GET", f"{_alp_conf()['BASE']}/v2/account")
    except Exception as e: return {"_error":str(e)}

def alp_positions():
    """Alpaca 보유 포지션 목록을 가져옵니다."""
    try: return _http_json("GET", f"{_alp_conf()['BASE']}/v2/positions")
    except Exception as e: return {"_error":str(e)}

def alp_orders_open():
    """Alpaca 열린 주문(미체결) 목록을 가져옵니다."""
    try: return _http_json("GET", f"{_alp_conf()['BASE']}/v2/orders", params={"status":"open","nested":"false"})
    except Exception as e: return {"_error":str(e)}

def alp_orders_all(limit=20):
    """Alpaca 모든 주문(체결, 취소 포함) 내역을 가져옵니다."""
    try: return _http_json("GET", f"{_alp_conf()['BASE']}/v2/orders", params={"status":"all","limit":limit,"nested":"false"})
    except Exception as e: return {"_error":str(e)}

def alp_order_cancel(oid):
    """특정 ID의 주문을 취소합니다."""
    try: return _http_json("DELETE", f"{_alp_conf()['BASE']}/v2/orders/{oid}")
    except Exception as e: return {"_error":str(e)}

def alp_order_cancel_all():
    """모든 열린 주문을 취소합니다."""
    try: return _http_json("DELETE", f"{_alp_conf()['BASE']}/v2/orders")
    except Exception as e: return {"_error":str(e)}

def alp_asset(sym):
    """특정 종목이 거래 가능한 자산인지 확인합니다."""
    try: return _http_json("GET", f"{_alp_conf()['BASE']}/v2/assets/{sym.upper()}")
    except Exception as e:
        if "404" in str(e): return None # 없는 종목은 None으로 처리
        return {"_error":str(e)}

def alp_place_order(sym, qty=None, side="buy", type_="market", limit_price=None, tif="day", extended=False, notional=None):
    """Alpaca에 주문을 전송합니다."""
    p={"symbol":sym.upper(),"side":side,"type":type_,"time_in_force":tif}
    if qty is not None:
        if str(qty).lower() == '100%':
             p['qty_is_percent'] = 'true'; p["qty"] = "100"
        else:
             p["qty"]=str(qty)
    if limit_price is not None: p["limit_price"]=f"{float(limit_price):.2f}"
    if extended and type_=="limit" and tif=="day": p["extended_hours"]=True
    if notional is not None: p["notional"]=f"{float(notional):.2f}"
    return _http_json("POST", f"{_alp_conf()['BASE']}/v2/orders", data=json.dumps(p))

def iex_intraday_bars(sym, timeframe, hours=48):
    """Alpaca를 통해 IEX의 분봉/시간봉 데이터를 가져옵니다. chart 명령어에서 사용됩니다."""
    end=datetime.now(ET_TZ); start=end - timedelta(hours=hours+1)
    try:
        js=_http_json("GET", f"{_alp_conf()['MKT']}/v2/stocks/{sym.upper()}/bars", params={"timeframe":timeframe,"start": start.astimezone(timezone.utc).isoformat()})
        return [{"t":b.get("t"),"o":b.get("o"),"h":b.get("h"),"l":b.get("l"),"c":b.get("c")} for b in js.get("bars",[])]
    except Exception:
        return []