# command.py
from ui_colors import color
from config import set_mode, get_mode, set_quote_source, get_quote_source, set_feed, get_feed, ui
from view_list import print_banner, render_info, render_list, render_orders, print_ticker_block
from view_chart import render_chart
from trade import buy_interactive, sell_interactive, cancel_interactive, buy_cli, sell_cli, cancel_all_orders
from api import alp_acct

help_text = """\
[기본]
  info / list / orders / .TICKER / chart .T [DAYS]

[모드/소스]
  live / paper
  source [stooq|iex]   (입력 없이 실행하면 현재 소스 표시 후 전환 질의)
  feed   [iex|sip]     (Alpaca 데이터 피드)

[주문]
  buy .T QTY [LIMIT]    (예: buy .AAPL 10 150.50)
  sell .T all|QTY [LIMIT] (예: sell .MSFT all)
  cancel [ID] / cancel all (ID 생략 시 대화형 모드)

[기타]
  diag / reload / help / quit
"""

def run_command(raw, state):
    if not raw: return state
    parts=raw.split(); cmd=parts[0].lower()
    if cmd.startswith(".") and len(cmd)>1:
        t=raw[1:].upper(); print_ticker_block(t); state["last_ticker"]=t; return state
    if cmd in ("?","help"): print(help_text); return state
    if cmd=="live":
        set_mode("LIVE"); print(color("!!! LIVE TRADING ENABLED !!!","bg_red")); print_banner()
        try: render_info()
        except: pass
        return state
    if cmd=="paper":
        set_mode("PAPER"); print_banner()
        try: render_info()
        except: pass
        return state
    if cmd=="source":
        if len(parts)==1:
            print(f"현재 시세 소스: {get_quote_source()}"); ans=input("변경? (stooq/iex/엔터=유지): ").strip().lower()
            if ans in ("stooq","iex"): set_quote_source(ans); print(f"시세 소스 전환: {ans.upper()}")
            return state
        set_quote_source(parts[1]); print(f"시세 소스 전환: {parts[1].upper()}"); return state
    if cmd=="feed":
        if len(parts)==1:
            print(f"현재 Alpaca 피드: {get_feed()}"); ans=input("변경? (iex/sip/엔터=유지): ").strip().lower()
            if ans in ("iex","sip"): set_feed(ans); print(f"피드 전환: {ans.upper()}")
            return state
        set_feed(parts[1]); print(f"피드 전환: {parts[1].upper()}"); return state
    if cmd=="diag":
        print("--- System Diagnostics ---")
        print(f"Trading Mode  : {get_mode()}"); print(f"Quote Source  : {get_quote_source()}")
        print("\n[Alpaca Configuration]")
        from config import get_config; cfg=get_config(); alp=cfg.get("alpaca",{})
        base=alp.get(get_mode().lower(),{}).get("base"); key=alp.get(get_mode().lower(),{}).get("key")
        print(f"Endpoint      : {base}"); print(f"API Key       : {key[:5]}...{key[-4:]}" if key else "Not Set")
        print(f"Market URL    : {alp.get('market')}"); print(f"Data Feed     : {get_feed().upper()}")
        print("\n[Alpaca Connection Status]")
        a=alp_acct(); ok="_error" not in a
        if ok:
            print(color("Connection    : 성공 (계좌 ID: {})".format(a.get("account_number")), "green"))
            print(f"Account Status: {a.get('status')}")
        else:
            print(color(f"Connection    : 실패", "bright_red")); print(f"Reason        : {a.get('_error')}")
        print("------------------------")
        return state
    if cmd=="info": render_info(); return state
    if cmd=="list": render_list(); return state
    if cmd=="orders": render_orders(20); return state
    if cmd=="chart":
        sym = parts[1][1:].upper() if len(parts)>=2 and parts[1].startswith(".") else (state.get("last_ticker") or "SOXL")
        days = int(parts[2]) if len(parts)>=3 and parts[2].isdigit() else 180
        U=ui(); render_chart(sym, days=days, width=int(U.get("chart_width",80)), height=int(U.get("chart_height",15)))
        return state
    if cmd=="buy":
        if len(parts)>=2 and parts[1].startswith("."):
            sym=parts[1][1:].upper(); qty_tok=parts[2] if len(parts)>=3 else None; price_tok=parts[3] if len(parts)>=4 else None
            buy_cli(sym, qty_tok, price_tok); return state
        else:
            buy_interactive(); return state
    if cmd=="sell":
        if len(parts)>=2 and parts[1].startswith("."):
            sym=parts[1][1:].upper(); qty_tok=parts[2] if len(parts)>=3 else None; price_tok=parts[3] if len(parts)>=4 else None
            sell_cli(sym, qty_tok, price_tok); return state
        else:
            sell_interactive(); return state
    if cmd=="cancel":
        if len(parts) > 1 and parts[1].lower() == "all":
            cancel_all_orders()
        else:
            order_id = parts[1] if len(parts) > 1 else None
            cancel_interactive(order_id)
        return state
    if cmd=="reload":
        from config import load_config; load_config(); print("설정 재적용 완료."); return state
    if cmd=="quit": state["quit"]=True; return state
    print("명령을 확인하세요. help"); return state