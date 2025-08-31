# core.py
# 프로그램 전반에서 사용되는 핵심 유틸리티 함수들을 모아놓은 파일입니다.
# 시간 처리, 안전한 타입 변환, 터미널 UI 정렬 등 기반이 되는 기능들을 담당합니다.

from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
import re

# --- 상수 정의 ---
ET_TZ = ZoneInfo("America/New_York")  # 미국 동부 시간대 (ET)
SEP = "  |  "  # 컬럼 구분자

# --- 시간 관련 함수 ---

def now_et():
    """현재 시간을 미국 동부 시간(ET) 기준으로 반환합니다."""
    return datetime.now(ET_TZ)

def dtfmt(dt, fmt):
    """datetime 객체를 주어진 포맷의 문자열로 변환합니다."""
    try:
        return dt.strftime(fmt)
    except:
        return str(dt)

def market_phase_et(dt=None):
    """주어진 시간이 미국 주식 시장의 어떤 단계인지 (정규장, 프리마켓 등) 반환합니다."""
    et = now_et() if dt is None else dt
    if et.weekday() >= 5: return "Closed"  # 주말은 휴장
    t = et.time()
    if dtime(4, 0) <= t < dtime(9, 30): return "Pre"
    if dtime(9, 30) <= t < dtime(16, 0): return "Regular"
    if dtime(16, 0) <= t < dtime(20, 0): return "After"
    return "Closed"

# --- 안전한 타입 변환 함수 ---

def safe_float(x, default=0.0):
    """값을 float으로 변환하되, 실패 시 기본값(0.0)을 반환합니다."""
    try:
        if x is None: return default
        return float(x)
    except (ValueError, TypeError):
        return default

def safe_int(x, default=0):
    """값을 int로 변환하되, 실패 시 기본값(0)을 반환합니다."""
    try:
        if x is None: return default
        return int(float(x))
    except (ValueError, TypeError):
        return default

# --- UI 정렬 관련 함수 ---

def _decimals():
    """설정 파일(userdefined.json)에서 소수점 자릿수 설정을 가져옵니다."""
    from config import ui
    return int(ui().get("decimals", 2))

def align_int_commas(vals):
    """숫자 리스트를 받아 천 단위 콤마를 찍고, 오른쪽 정렬된 문자열 리스트로 반환합니다."""
    parts = [f"{int(round(safe_float(v))):,d}" if v is not None and str(v).strip() != '' else "-" for v in vals]
    width = max((len(x) for x in parts), default=0)
    return [p.rjust(width) for p in parts], width

def align_money_signed(vals, decimals=None, show_plus=False):
    """
    금액 리스트를 받아 '$' 기호를 붙이고 소수점 기준으로 정렬된 문자열 리스트로 반환합니다.
    최종적으로 '-$1,234.56'과 같은 포맷을 보장합니다.
    """
    if decimals is None: decimals = _decimals()
    parsed = []
    for v in vals:
        try:
            f = safe_float(v); sign = ""
            if f < 0: sign = "-"
            elif show_plus and f > 0: sign = "+"
            s = f"{abs(f):,.{decimals}f}"; ip, _, fp = s.partition(".")
            parsed.append((sign, ip, fp))
        except (ValueError, TypeError):
            parsed.append(None)

    if not parsed: return [], 0
    max_len_int_part = max((len(p[1]) for p in parsed if p is not None), default=0)
    
    output_list = []
    for p in parsed:
        if p is None:
            output_list.append("-")
            continue
        sign, int_part, frac_part = p
        # 부호와 달러 기호를 숫자와 합친 후, 정수부 길이에 맞춰 정렬
        num_str = f"{sign}${int_part}"
        padded_num_str = num_str.rjust(max_len_int_part + 2) # 부호(1), 달러(1) 감안
        output_list.append(f"{padded_num_str}.{frac_part}")

    max_width = max((len(s) for s in output_list), default=0)
    
    # 색상 코드가 포함될 수 있으므로, 최종 정렬은 보이는 텍스트 기준으로 다시 수행
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    aligned_list = []
    for s in output_list:
        visible_len = len(ansi_escape.sub('', s))
        padding = " " * (max_width - visible_len)
        aligned_list.append(padding + s)
        
    return aligned_list, max_width


def two_cols_fixed(left_lines, right_lines, left_w, auto_left_width=False, enforce_sep=False):
    ansi_escape = _re.compile(r'\x1b\[[0-9;]*m')
    L = left_lines or []
    R = right_lines or []
    n = max(len(L), len(R))
    if len(L) < n: L = L + [""] * (n - len(L))
    if len(R) < n: R = R + [""] * (n - len(R))
    if auto_left_width:
        l_max = 0
        for l in L:
            l_visible_len = len(ansi_escape.sub('', l))
            if l_visible_len > l_max: l_max = l_visible_len
        left_w = l_max
    out = []
    for i in range(n):
        l = L[i] or ""
        r = R[i] or ""
        l_visible_len = len(ansi_escape.sub('', l))
        padding = " " * (left_w - l_visible_len) if left_w > l_visible_len else ""
        r_visible = ansi_escape.sub('', r).strip()
        sep = SEP if (enforce_sep or r_visible) else ""
        out.append(l + padding + sep + r)
    return out

# --- GRID RENDERERS ----------------------------------------------------------
import re as _re
def _ansi_visible_len(s: str) -> int:
    _ansi = _re.compile(r'\x1b\[[0-9;]*m')
    return len(_ansi.sub('', s))

def generate_grid_view(items, cols=4, padding=2):
    if not items: return []
    rows = (len(items) + cols - 1) // cols
    col_widths = [0] * cols
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            if idx < len(items):
                w = _ansi_visible_len(str(items[idx]))
                if w > col_widths[c]: col_widths[c] = w
    lines = []
    for r in range(rows):
        parts = []
        for c in range(cols):
            idx = r * cols + c
            s = str(items[idx]) if idx < len(items) else ""
            pad = " " * (col_widths[c] - _ansi_visible_len(s))
            parts.append(s + pad)
        lines.append((" " * padding).join(parts).rstrip())
    return lines

def generate_grid_view_colmajor(items, cols=4, padding=2):
    if not items: return []
    n = len(items)
    rows = (n + cols - 1) // cols
    col_widths = [0] * cols
    grid = [["" for _ in range(cols)] for __ in range(rows)]
    idx = 0
    for c in range(cols):
        for r in range(rows):
            if idx < n:
                s = str(items[idx])
                grid[r][c] = s
                w = _ansi_visible_len(s)
                if w > col_widths[c]: col_widths[c] = w
                idx += 1
    lines = []
    for r in range(rows):
        parts = []
        for c in range(cols):
            s = grid[r][c]
            pad = " " * (col_widths[c] - _ansi_visible_len(s))
            parts.append(s + pad)
        lines.append((" " * padding).join(parts).rstrip())
    return lines


# --- FIXED-WIDTH TABLE RENDERER (ANSI-safe) ----------------------------------
def render_fixed_table(headers, rows, aligns=None, padding=2):
    """
    headers: list[str]
    rows   : list[list[str]]
    aligns : list['left'|'right'|'center'] per column
    Returns: list[str] lines with fixed-width columns, ANSI-safe.
    """
    if headers is None: headers = []
    rows = rows or []
    ncol = len(headers)
    if aligns is None: aligns = ["left"] * ncol
    _ansi = _re.compile(r'\x1b\[[0-9;]*m')
    def vis(s): return len(_ansi.sub('', str(s)))
    widths = [0]*ncol
    for ci in range(ncol):
        widths[ci] = max(vis(headers[ci]), max((vis(r[ci]) for r in rows if ci < len(r)), default=0))
    def pad_cell(text, ci):
        s = str(text)
        pad = widths[ci] - vis(s)
        if aligns[ci] == "right":
            return " " * pad + s
        elif aligns[ci] == "center":
            left = pad // 2; right = pad - left
            return " " * left + s + " " * right
        else:
            return s + " " * pad
    lines = []
    lines.append((" " * padding).join(pad_cell(headers[c], c) for c in range(ncol)))
    for r in rows:
        lines.append((" " * padding).join(pad_cell(r[c], c) for c in range(ncol)))
    return lines
