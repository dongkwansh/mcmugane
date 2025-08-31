# view_list.py
# info, list, orders, .TICKER 등 주요 정보 화면을 터미널에 그리는(렌더링) 역할을 합니다.
# core.py의 정렬 함수와 api.py의 데이터 함수를 조합하여 사용자에게 보여줄 최종 UI를 만듭니다.

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import hashlib
import re

from config import ui, get_mode, baskets as cfg_baskets, ticker_color_map
from core import now_et, dtfmt, market_phase_et, SEP, align_money_signed, align_int_commas, two_cols_fixed, safe_float, safe_int, generate_grid_view, render_fixed_table, generate_grid_view_colmajor
from ui_colors import color, colorize_delta_money, up_down_color
from api import alp_acct, alp_positions, alp_orders_all, stooq_light

ET_TZ = ZoneInfo("America/New_York")

BASE_FG='bright_white'
def _print_base(text:str):
    try:
        U=ui(); c=U.get('base_text_color','bright_white')
    except Exception:
        c='bright_white'
    print(color(text, c))

# --- 유틸리티 함수 ---
def _iso_to_et_fmt(iso_str: str) -> str:
    """API가 반환하는 ISO 형식의 날짜 문자열을 사용자 친화적인 포맷으로 변환합니다."""
    if not iso_str: return ""
    # Alpaca의 다양한 날짜 포맷(Z, +00:00, 마이크로/나노초)을 모두 처리
    try:
        # T와 . 사이의 시간 부분만 잘라내어 파싱
        s = iso_str.split('T')[0] + ' ' + iso_str.split('T')[1].split('.')[0]
        dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        et = dt.astimezone(ET_TZ)
        return dtfmt(et, ui().get("datetime_format", "%m-%d-%y %H:%M:%S"))
    except Exception:
        # 아주 오래된 포맷(예: 03-10-22 10:59:26) 처리
        try:
            dt = datetime.strptime(iso_str, '%m-%d-%y %H:%M:%S')
            return dtfmt(dt, ui().get("datetime_format", "%m-%d-%y %H:%M:%S"))
        except:
             return "--- PARSE ERROR ---".center(19)

_PALETTE = ["bright_cyan", "bright_yellow", "bright_magenta", "bright_green", "bright_red", "bright_blue", "cyan", "yellow", "magenta", "green", "red", "blue", "bright_white", "white", "bright_black"]
def _sym_color(sym:str):
    """종목 심볼에 고유한 색상을 부여합니다. 설정 파일에 지정된 색상을 우선 적용합니다."""
    cmap = ticker_color_map()
    name = cmap.get(sym.upper())
    if name: return name
    h=int(hashlib.sha1(sym.upper().encode()).hexdigest(),16)
    return _PALETTE[h % len(_PALETTE)]

def _pick_unique_color(sym:str, used:set):
    """한 화면 내에서 종목별 색상이 겹치지 않도록 조정합니다."""
    c=_sym_color(sym)
    if c not in used: used.add(c); return c
    try: idx=_PALETTE.index(c)
    except ValueError: idx=0
    for step in range(1,len(_PALETTE)):
        c2=_PALETTE[(idx+step)%len(_PALETTE)]
        if c2 not in used: used.add(c2); return c2
    return c

# --- 화면 렌더링 함수 ---
def print_banner():
    """프로그램 상단에 현재 모드와 시간 정보를 표시하는 배너를 출력합니다."""
    U=ui(); et=now_et()
    line=f"[{get_mode()} Mode] {dtfmt(et, U.get('datetime_format','%m-%d-%y %H:%M:%S'))}, Session : {market_phase_et(et)}"
    deco=color(line, "bg_magenta") if get_mode()=="LIVE" else color(line,"bright_black")
    print(deco)


def render_info():
    """'info' 명령어에 대한 화면을 출력합니다. 계좌의 종합 정보를 보여줍니다."""
    U=ui(); et=now_et(); acct=alp_acct()
    if "_error" in acct: print("[ACCOUNT] Alpaca 접근 불가 — "+acct["_error"]); return
    equity=safe_float(acct.get("equity")); last_equity=safe_float(acct.get("last_equity"))
    pnl_abs=equity-last_equity; pnl_pct=(pnl_abs/last_equity*100.0) if last_equity else 0.0

    # 왼쪽 컬럼 구성 (금액 열 폭을 먼저 산정)
    Lk=["Equity","Portfolio","Cash","BP(Total)","BP(RegT)","BP(DT)","LMV","SMV","Maint.Margin","SMA"]
    Lv=[equity, safe_float(acct.get("portfolio_value")), safe_float(acct.get("cash")), safe_float(acct.get("buying_power")),
        safe_float(acct.get("regt_buying_power")), 0.0, safe_float(acct.get("long_market_value")), safe_float(acct.get("short_market_value")),
        safe_float(acct.get("maintenance_margin")), safe_float(acct.get("sma"))]
    mfmt, _ = align_money_signed(Lv, show_plus=False)

    # 공통 폭 계산(ANSI 제거한 보이는 길이)
    import re as _re
    _ansi=_re.compile(r'\x1b\[[0-9;]*m')
    maxw=0
    for _s in mfmt:
        vlen=len(_ansi.sub('', _s))
        if vlen>maxw: maxw=vlen

    # P/L Today 문구(금액만 동일 폭으로 패딩 + %)
    _pl, _ = align_money_signed([pnl_abs], show_plus=False)
    _plm = _pl[0].strip()
    _pad = ' '*(maxw - len(_plm))
    _arrow = '▲' if pnl_abs>=0 else '▼'
    pl_line_colored = color(f"{_pad}{_arrow} {_plm} ({pnl_pct:.2f}%)", up_down_color(pnl_abs))

    Lk2 = Lk + ["P/L Today"]
    mfmt2 = mfmt + [pl_line_colored]
    Llines=[f"{k:<13}: {v}" for k,v in zip(Lk2,mfmt2)]

    # 오른쪽 컬럼
    Rk=["Acct#","Status","Currency","Multiplier","PDT","Shorting","DayTrades","Updated"]
    Rv=[acct.get("account_number"), acct.get("status"), acct.get("currency"), safe_int(acct.get("multiplier") or 2),
        "Y" if acct.get("pattern_day_trader") else "N",
        "Y" if acct.get("shorting_enabled") else "N", safe_int(acct.get("daytrade_count")), ""]
    Rlines=[f"{k:<12}: {v}" for k,v in zip(Rk,Rv)]

    left_w=int(U.get("fixed_left_width",34))
    header=f"=== ACCOUNT  |  {dtfmt(et, U.get('datetime_format','%m-%d-%y %H:%M:%S'))} ET Alpaca"
    _print_base(header)
    for _ln in two_cols_fixed(Llines, ["[STATUS]"]+Rlines, left_w, auto_left_width=True, enforce_sep=True):
        print(_ln)


def render_list():
    """'list' 명령어 화면 — 좌측 바스켓(내림차순, 컬럼-우선), 우측 포지션(고정폭 표)"""
    U=ui()
    # Left: Baskets
    L=["[Baskets]"]
    bks=cfg_baskets()
    if not bks:
        L.append("(정의된 바스켓 없음)")
    else:
        for name, weights in bks.items():
            L.append(f"{name}:")
            sorted_weights = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
            used=set()
            items=[f"{color(f'{s.upper():<5}', _pick_unique_color(s, used))} {float(w)*100:>6.2f}%" for s,w in sorted_weights]
            L.extend(generate_grid_view_colmajor(items, cols=int(U.get("baskets_per_line",4)), padding=2))

    # Right: Positions
    R=["[Positions]"]
    R.extend(_build_positions_table())

    left_w=int(U.get("fixed_left_width",34))
    header = f"=== LIST  |  {dtfmt(now_et(), U.get('datetime_format','%m-%d-%y %H:%M:%S'))} ET Baskets/Positions"
    _print_base(header)
    for _ln in two_cols_fixed(L, R, left_w, auto_left_width=True, enforce_sep=True):
        print(_ln)


def render_orders(limit=20):
    """'orders' 화면: 고정폭 컬럼(ANSI-safe)으로 행/열 완전 정렬"""
    U=ui(); od=alp_orders_all(limit=limit)
    if isinstance(od,dict) and "_error" in od:
        print("[Orders] 불러오기 실패 — "+od["_error"]); return
    if not od:
        print("(주문 없음)"); return
    rows=[]
    for o in od:
        sym = (o.get("symbol","") or "")[:6].upper()
        side = (o.get("side","") or "").lower()
        qty  = safe_int(o.get("qty") or o.get("filled_qty") or 0)
        typ  = (o.get("type") or o.get("order_type") or "").lower()
        lim  = o.get("limit_price")
        limf = safe_float(lim) if lim not in (None,"") else None
        lims,_ = align_money_signed([limf if limf is not None else 0.0], show_plus=False)
        lim_s = lims[0].strip() if limf is not None else "-"
        subm = _iso_to_et_fmt(o.get("submitted_at") or o.get("created_at") or "")
        status = (o.get("status") or "").lower()
        fqty = safe_int(o.get("filled_qty") or 0)
        favg = safe_float(o.get("filled_avg_price"))
        fpxs,_ = align_money_signed([favg if favg is not None else 0.0], show_plus=False)
        filled = "-" if fqty==0 and favg in (None,0.0) else f"{fqty:,d} @ {fpxs[0].strip()}"
        fat  = _iso_to_et_fmt(o.get("filled_at") or "")
        rows.append([sym, side, f"{qty:,d}", typ, lim_s, subm, status, filled, fat])
    headers = ["Sym.","Side","Qty","Type","Limit","Submitted","Status","Filled","FilledAt"]
    aligns  = ["left","left","right","left","right","left","left","left","left"]
    lines = render_fixed_table(headers, rows, aligns, padding=2)
    for i, ln in enumerate(lines):
        print(ln)

def print_ticker_block(sym):
    """'.TICKER' 명령어에 대한 화면을 출력합니다. Stooq 데이터를 사용합니다."""
    U=ui(); info=stooq_light(sym)
    if not info: print(f"[{sym}] 시세 없음"); return
    o_,h_,l_,c_,vol=info["Open"], info["High"], info["Low"], info["Close"], info["Volume"]
    prices_formatted, _ = align_money_signed([o_, h_, l_, c_], show_plus=False)
    o, h, l, p = prices_formatted
    v1,_ = align_int_commas([vol])
    delta = safe_float(c_)-safe_float(o_); pct = (delta/safe_float(o_)*100.0) if safe_float(o_) else 0.0
    price_line = f"Price : {p.strip()}  {colorize_delta_money(delta, pct, U.get('color_scheme','us'), int(U.get('decimals',2)))}"
    pos=alp_positions(); hold=["(보유 없음)"]
    if not (isinstance(pos,dict) and "_error" in pos) and pos:
        for it in pos:
            if (it.get("symbol","") or "").upper()==sym.upper():
                q=safe_int(it.get("qty"))
                if q>0:
                    avg=safe_float(it.get("avg_entry_price")); mv=safe_float(it.get("market_value"))
                    a_s,_=align_money_signed([avg], show_plus=False); m_s,_=align_money_signed([mv],  show_plus=False)
                    hold=[f"Qty {q:,d} @ {a_s[0].strip()}", f"      = {m_s[0].strip()}"]
                break
    L=[f"Open  : {o}", f"High  : {h}", f"Low   : {l}", price_line]
    R=[f"Volume: {v1[0]}", "[HOLDING]"]+hold
    title = f"=== {color(sym.upper(), _sym_color(sym))} | {dtfmt(now_et(), U.get('datetime_format','%m-%d-%y %H:%M:%S'))} ET (Stooq)"
    left_w=int(U.get("fixed_left_width",34))
    print(two_cols_fixed([title]+L, R, left_w))


def _build_positions_table():
    U = ui()
    pos = alp_positions()
    if isinstance(pos, dict) and "_error" in pos:
        return ["(Positions 불러오기 실패 — " + pos["_error"] + ")"]
    rows = []
    used_pos_colors = set()
    for it in pos or []:
        sym = (it.get("symbol","") or "")[:6].upper()
        qty = f"{safe_int(it.get('qty')):,d}"
        avg = safe_float(it.get('avg_entry_price'))
        mv  = safe_float(it.get('market_value'))
        a_s,_ = align_money_signed([avg], show_plus=False)
        m_s,_ = align_money_signed([mv ], show_plus=False)
        sym_col = color(f"{sym:<5}", _pick_unique_color(sym, used_pos_colors))
        rows.append([sym_col, qty, a_s[0].strip(), m_s[0].strip()])
    headers = ["Sym.","Qty","AvgPrice","MktValue"]
    aligns  = ["left","right","right","right"]
    return render_fixed_table(headers, rows, aligns, padding=2)
