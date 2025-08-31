from __future__ import annotations
import os, json, uuid, asyncio, logging
from pathlib import Path
from typing import Dict, Any, List, Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import CONFIG_DIR, ALGORITHM_DIR, LOG_DIR
from app.engine.broker import AccountConfig, AlpacaBroker
from app.engine.trade_engine import EngineManager, RunConfig
from app.display import display
from app import auth

app = FastAPI(title="MCMUGANE Autotrader", version="1.2")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / "server.log"), logging.StreamHandler()]
)
logger = logging.getLogger("server")
engine = EngineManager()

# ---------- helpers ----------
def load_accounts() -> Dict[str, Any]:
    p = CONFIG_DIR / "accounts.json"
    if not p.exists():
        return {}
    with open(p, "r") as f:
        return json.load(f)

def load_algorithms() -> List[Dict[str, Any]]:
    algos = []
    for fp in sorted(ALGORITHM_DIR.glob("*.json")):
        try:
            with open(fp, "r") as f:
                spec = json.load(f)
                spec["_file"] = fp.name
                algos.append(spec)
        except Exception as e:
            logger.exception("Failed loading %s: %s", fp, e)
    return algos

def get_algo_by_file(name: str) -> Dict[str, Any]:
    with open(ALGORITHM_DIR / name, "r") as f:
        return json.load(f)

def make_broker_from_account_id(acc_id: str) -> AlpacaBroker:
    accounts = load_accounts()
    if acc_id not in accounts:
        raise HTTPException(400, f"Unknown account_id {acc_id}")
    acc_data = accounts[acc_id]
    acc = AccountConfig(id=acc_id, broker=acc_data.get("broker","alpaca"), name=acc_data.get("name", acc_id),
                        paper=acc_data.get("paper", True), api_key=acc_data["api_key"], secret_key=acc_data["secret_key"])
    return AlpacaBroker(acc)

# ---------- pages ----------
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    # 인증 없으면 로그인으로
    try:
        auth.require_auth(request)
    except Exception:
        return FileResponse(str(Path(__file__).parent / "static" / "login.html"))
    return FileResponse(str(Path(__file__).parent / "static" / "index.html"))

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return FileResponse(str(Path(__file__).parent / "static" / "login.html"))

# ---------- auth api ----------
@app.post("/api/login")
def api_login(payload: Dict[str, Any]):
    users = auth.load_users().get("users", [])
    u = next((u for u in users if u.get("username") == payload.get("username")), None)
    if not u:
        raise HTTPException(401, "invalid_credentials")
    if not auth.verify_password(payload.get("password", ""), u.get("salt", ""), u.get("password_hash", "")):
        raise HTTPException(401, "invalid_credentials")
    token = auth.create_token(u["username"], minutes=12*60)
    return {"token": token, "user": u["username"]}

@app.get("/api/me")
def api_me(request: Request):
    user = auth.require_auth(request)
    return {"user": user}

# ---------- protected apis ----------
@app.get("/api/accounts")
def api_accounts(request: Request):
    auth.require_auth(request)
    data = load_accounts()
    return [{"id": k, "name": v.get("name", k), "broker": v.get("broker","alpaca"), "paper": v.get("paper", True)} for k,v in data.items()]

@app.get("/api/algorithms")
def api_algorithms(request: Request):
    auth.require_auth(request)
    return load_algorithms()

@app.get("/api/runs")
def api_runs(request: Request):
    auth.require_auth(request)
    return engine.list_runs()

@app.post("/api/start")
async def api_start(payload: Dict[str, Any], request: Request):
    auth.require_auth(request)
    accounts = load_accounts()
    acc_id = payload.get("account_id")
    if acc_id not in accounts:
        raise HTTPException(400, f"Unknown account_id {acc_id}")
    acc_data = accounts[acc_id]
    acc = AccountConfig(id=acc_id, broker=acc_data.get("broker","alpaca"), name=acc_data.get("name", acc_id),
                        paper=acc_data.get("paper", True), api_key=acc_data["api_key"], secret_key=acc_data["secret_key"])
    algo_file = payload.get("algorithm_file")
    symbols = payload.get("symbols", [])
    if isinstance(symbols, str):
        symbols = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbols:
        raise HTTPException(400, "symbols required")
    spec = get_algo_by_file(algo_file)
    sizing = payload.get("sizing", {"type":"notional","value":100.0})
    run_id = payload.get("run_id") or str(uuid.uuid4())[:8]
    cfg = RunConfig(run_id=run_id, account=acc, symbols=symbols, strategy_spec=spec, sizing=sizing,
                    timeframe=spec.get("timeframe","1Min"), lookback_minutes=int(spec.get("lookback_minutes", 120)))
    await engine.start(cfg, ws_send=conn_mgr.broadcast)
    return {"ok": True, "run_id": run_id}

@app.post("/api/stop")
async def api_stop(payload: Dict[str, Any], request: Request):
    auth.require_auth(request)
    rid = payload.get("run_id")
    if not rid:
        raise HTTPException(400, "run_id required")
    await engine.stop(rid)
    return {"ok": True}

# ---------- websocket (auth via token query) ----------
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: str):
        for ws in list(self.active):
            try:
                await ws.send_text(message)
            except Exception:
                pass

conn_mgr = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # token 검사
    try:
        token = websocket.query_params.get('token')
        if not token:
            await websocket.close(code=4401)
            return
        auth.verify_token(token)
    except Exception:
        await websocket.close(code=4401)
        return

    await conn_mgr.connect(websocket)
    conn_id = str(id(websocket))
    display.set_format(conn_id, "table")
    try:
        await websocket.send_text("Connected. Type HELP for commands. FORMAT table|json to toggle output.")
        while True:
            data = await websocket.receive_text()
            out = await handle_command(data, websocket.send_text, conn_id)
            if out:
                await websocket.send_text(out)
    except WebSocketDisconnect:
        conn_mgr.disconnect(websocket)

# ---------- terminal commands ----------
async def handle_command(cmd: str, send: Callable[[str], Any], conn_id: str):
    parts = cmd.strip().split()
    if not parts:
        return ""
    op = parts[0].upper()
    args = parts[1:]

    def kv_parse(items: List[str]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for p in items:
            if "=" in p:
                k, v = p.split("=", 1)
                out[k.lower()] = v
        return out

    if op == "HELP":
        return (
            "Commands:\n"
            "  FORMAT [table|json]\n"
            "  ACCOUNTS\n"
            "  ALGOS\n"
            "  ALGO SHOW <file.json>\n"
            "  RUNS\n"
            "  START account=<id> algo=<file.json> symbols=AAPL,MSFT size=qty:10|notional:200\n"
            "  STOP run=<id>\n"
            "  POS [account=<id>]\n"
            "  ORDERS [account=<id>] [status=open|closed|all]\n"
            "  BUY <SYM> size=qty:10|notional:200 [tp=2] [sl=1] [tif=day] [account=<id>]\n"
            "  SELL <SYM> size=qty:10|notional:200 [tp=2] [sl=1] [tif=day] [account=<id>]\n"
            "  LIMITBUY <SYM> qty=10 price=123.45 [tif=day] [account=<id>]\n"
            "  LIMITSELL <SYM> qty=10 price=123.45 [tif=day] [account=<id>]\n"
            "  CANCEL ALL [account=<id>]\n"
        )

    if op == "FORMAT":
        if args:
            fmt = args[0].lower()
            display.set_format(conn_id, fmt)
        return f"FORMAT={display.get_format(conn_id)}"

    accounts = load_accounts()
    default_acc = list(accounts.keys())[0] if accounts else None

    if op in ("ACCOUNTS", "ACCOUNT", "ACCT"):
        out = [{"id": k, **v} for k, v in accounts.items()]
        return display.render(conn_id, out, headers=["id","name","broker","paper"])

    if op in ("ALGOS", "ALGORITHMS"):
        algos = load_algorithms()
        out = [{"file": a.get("_file"), "name": a.get("name"), "timeframe": a.get("timeframe")} for a in algos]
        return display.render(conn_id, out, headers=["file","name","timeframe"])

    if op == "ALGO" and len(args) >= 2 and args[0].upper() == "SHOW":
        spec = get_algo_by_file(args[1])
        return display.render(conn_id, spec)

    if op == "RUNS":
        return display.render(conn_id, engine.list_runs(), headers=["run_id","running","symbols"])

    if op == "START":
        kv = kv_parse(args)
        acc_id = kv.get("account") or default_acc
        algo = kv.get("algo")
        symbols = [s.strip().upper() for s in (kv.get("symbols","")).split(",") if s.strip()]
        size = kv.get("size","notional:100")
        stype, sval = size.split(":",1)
        sizing = {"type": stype, "value": float(sval)}
        run_id = str(uuid.uuid4())[:8]
        payload = {"account_id": acc_id, "algorithm_file": algo, "symbols": symbols, "sizing": sizing, "run_id": run_id}
        await api_start(payload, Request)  # type: ignore (not used here)
        await send(display.render(conn_id, {"started_run_id": run_id}))
        return ""

    if op == "STOP":
        rid = None
        for p in args:
            if p.startswith("run="):
                rid = p.split("=",1)[1]
        if not rid:
            return "Usage: STOP run=<id>"
        await engine.stop(rid)
        return display.render(conn_id, {"stopped_run_id": rid})

    if op == "POS":
        kv = kv_parse(args)
        acc_id = kv.get("account") or default_acc
        br = make_broker_from_account_id(acc_id)
        pos = br.get_positions()
        return display.render(conn_id, pos, headers=["symbol","qty","avg_entry_price","market_value","unrealized_pl","unrealized_plpc"])

    if op == "ORDERS":
        kv = kv_parse(args)
        acc_id = kv.get("account") or default_acc
        status = kv.get("status")
        br = make_broker_from_account_id(acc_id)
        orders = br.get_orders(status=status)
        norm = []
        for o in orders:
            d = {k: str(v) for k,v in (o.__dict__ if hasattr(o, "__dict__") else dict(o)).items()}
            keep = {k: d.get(k) for k in ("id","client_order_id","symbol","side","qty","notional","type","time_in_force","status","created_at") if k in d}
            norm.append(keep)
        return display.render(conn_id, norm, headers=["id","symbol","side","qty","notional","type","time_in_force","status","created_at"])

    if op in ("BUY","SELL"):
        if not args:
            return "Usage: BUY <SYM> size=qty:10|notional:200 [tp=2] [sl=1] [tif=day] [account=<id>]"
        symbol = args[0].upper()
        kv = kv_parse(args[1:])
        side = op.lower()
        acc_id = kv.get("account") or default_acc
        sz = kv.get("size","notional:100")
        stype, sval = sz.split(":",1)
        tif = kv.get("tif","day")
        tp = float(kv.get("tp", "0") or 0) or None
        sl = float(kv.get("sl", "0") or 0) or None
        br = make_broker_from_account_id(acc_id)
        order_kwargs: Dict[str, Any] = {"tif": tif}
        if stype == "qty":
            order_kwargs["qty"] = float(sval)
        else:
            order_kwargs["notional"] = float(sval)
        if tp is not None:
            order_kwargs["take_profit"] = tp
        if sl is not None:
            order_kwargs["stop_loss"] = sl
        out = br.market_order(symbol=symbol, side=side, **order_kwargs)
        return display.render(conn_id, out)

    if op in ("LIMITBUY","LIMITSELL"):
        if not args:
            return "Usage: LIMITBUY <SYM> qty=10 price=123.45 [tif=day] [account=<id>]"
        symbol = args[0].upper()
        kv = kv_parse(args[1:])
        side = "buy" if op=="LIMITBUY" else "sell"
        acc_id = kv.get("account") or default_acc
        qty = float(kv.get("qty","0"))
        price = float(kv.get("price","0"))
        tif = kv.get("tif","day")
        br = make_broker_from_account_id(acc_id)
        out = br.limit_order(symbol=symbol, side=side, qty=qty, limit_price=price, tif=tif)
        return display.render(conn_id, out)

    if op == "CANCEL" and args and args[0].upper() == "ALL":
        kv = kv_parse(args[1:])
        acc_id = kv.get("account") or default_acc
        br = make_broker_from_account_id(acc_id)
        res = br.cancel_all()
        info = {"cancelled": len(res) if hasattr(res, "__len__") else "ok"}
        return display.render(conn_id, info)

    return "Unknown command."
