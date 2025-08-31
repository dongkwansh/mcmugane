import json, pathlib

_CFG = None
_STATE = {"mode":"PAPER","quote_source":"STOOQ","feed":"iex"}

def load_config(path="userdefined.json"):
    global _CFG
    p = pathlib.Path(path)
    _CFG = json.loads(p.read_text(encoding="utf-8"))
    print(f"[config] loaded: {p.resolve()}")
    alp = _CFG.get("alpaca", {})
    _STATE["feed"] = alp.get("feed","iex").lower()
    return _CFG

def get_config():
    global _CFG
    if _CFG is None: load_config()
    return _CFG

def set_mode(mode:str): _STATE["mode"]="LIVE" if str(mode).upper()=="LIVE" else "PAPER"
def get_mode(): return _STATE["mode"]

def set_quote_source(src:str): _STATE["quote_source"]="IEX" if str(src).upper()=="IEX" else "STOOQ"
def get_quote_source(): return _STATE["quote_source"]

def set_feed(feed:str): _STATE["feed"]="sip" if str(feed).lower()=="sip" else "iex"
def get_feed(): return _STATE["feed"]

def get_prompt_prefix(): return "L>>>" if _STATE["mode"]=="LIVE" else "P>>>"

def ui(): return get_config().get("ui", {})
def ticker_color_map(): return get_config().get("ticker_colors", {})
def baskets(): return get_config().get("baskets", {})
# config.py 에 아래 함수 추가

def get_alpha_vantage_key():
    """Alpha Vantage API 키를 설정 파일에서 가져옵니다."""
    return get_config().get("alpha_vantage_key")