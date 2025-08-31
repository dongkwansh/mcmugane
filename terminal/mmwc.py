import sys
from ui_colors import color
from config import load_config, get_mode, get_prompt_prefix, set_mode, set_quote_source, set_feed, ui
from view_list import print_banner, render_info
from command import run_command

def _colored_prompt():
    p=get_prompt_prefix()
    return color(p, "bright_magenta") if get_mode()=="LIVE" else color(p,"bright_cyan")

def main():
    load_config()
    args=[a.lower() for a in sys.argv[1:]]
    if "live" in args: set_mode("LIVE")
    if "paper" in args: set_mode("PAPER")
    if "iex" in args: set_quote_source("IEX")
    if "stooq" in args: set_quote_source("STOOQ")
    if "sip" in args: set_feed("sip")

    print_banner()
    try: render_info()
    except: pass
    print("(도움말: help 또는 ?)")

    state={"quit":False,"last_ticker":None}
    while not state["quit"]:
        try: raw=input(_colored_prompt()+" ").strip()
        except (EOFError,KeyboardInterrupt): break
        state=run_command(raw, state)

if __name__=="__main__":
    main()
