# ui_colors.py
COLORS = {
    "reset": "\033[0m", "bold": "\033[1m",
    "black": "\033[30m", "red": "\033[31m", "green": "\033[32m",
    "yellow": "\033[33m", "blue": "\033[34m", "magenta": "\033[35m",
    "cyan": "\033[36m", "white": "\033[37m",
    "bright_black": "\033[90m", "bright_red": "\033[91m", "bright_green": "\033[92m",
    "bright_yellow": "\033[93m", "bright_blue": "\033[94m",
    "bright_magenta": "\033[95m", "bright_cyan": "\033[96m",
    "bright_white": "\033[97m",
    "bg_magenta": "\033[45m", "bg_red": "\033[41m", "bg_green": "\033[42m"
}

def color(txt, name):
    c = COLORS.get(name, "")
    r = COLORS["reset"] if c else ""
    return f"{c}{txt}{r}"

def up_down_color(delta, scheme="us"):
    if delta is None: return lambda s: s
    if scheme == "kr":
        up_c, down_c = "red", "blue"
    else:
        up_c, down_c = "green", "red"
    
    if delta > 0: return lambda s: color(s, up_c)
    if delta < 0: return lambda s: color(s, down_c)
    return lambda s: color(s,"bright_black")

def delta_icon(delta):
    return "▲" if delta>0 else "▼" if delta<0 else "▬"

def colorize_delta_money(delta, pct=None, scheme="us", decimals=2):
    icon = delta_icon(delta)
    sign = "-" if delta < 0 else ""
    absv = abs(float(delta))
    
    # $ 기호는 부호 바로 뒤에 붙임
    base = f"{icon} {sign}${absv:,.{decimals}f}"
    
    if pct is not None:
        psign = "-" if pct < 0 else ""
        base += f" ({psign}{abs(float(pct)):.{decimals}f}%)"
        
    return up_down_color(delta, scheme)(base)