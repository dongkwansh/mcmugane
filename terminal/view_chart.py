# view_chart.py
# 'chart' 명령어에 대한 화면을 그리는 역할을 합니다.
# API로부터 시계열 데이터를 받아와 터미널 환경에 맞는 텍스트 기반 차트를 생성합니다.

from core import dtfmt, now_et, SEP, align_money_signed
from config import ui, get_quote_source
from api import stooq_daily, iex_intraday_bars
from ui_colors import color, up_down_color
from view_list import _sym_color
import math

def _get_chart_data(sym, days):
    """
    조회 기간(days)에 따라 최적의 데이터를 가져옵니다.
    - 5일 이하: IEX의 분봉/시간봉 데이터 우선 조회 (단기 추세 확인용)
    - 5일 초과 또는 IEX 데이터 실패 시: Stooq의 일봉 데이터 조회 (장기 추세 확인용)
    """
    bars = []
    source_name = "Stooq (Daily)" # 기본 소스

    # 5일 이하 단기 차트는 IEX 데이터를 먼저 시도
    if days <= 5:
        # 1일은 5분봉, 2~3일은 15분봉, 4~5일은 1시간봉으로 데이터 밀도 자동 조절
        timeframe = '5Min' if days <= 1 else ('15Min' if days <=3 else '1Hour')
        hours = 12 if days == 1 else 24 * days # 1일은 12시간, 그 외엔 전체 시간
        
        bars_iex = iex_intraday_bars(sym, timeframe=timeframe, hours=hours)
        if bars_iex:
            bars = [{"t": b["t"], "c": float(b["c"])} for b in bars_iex]
            source_name = f"IEX ({timeframe})"

    # IEX 데이터가 없거나, 5일을 초과하는 장기 차트일 경우 Stooq 데이터 사용
    if not bars:
        d = stooq_daily(sym, days=days + 5) # 데이터 끝부분이 잘리지 않도록 여유분 요청
        bars = [{"t": x["t"], "c": float(x["c"])} for x in d][-days:]
        source_name = "Stooq (Daily)"

    return bars, source_name

def _resample(vals, width):
    """데이터 포인트가 차트 너비보다 많을 경우, 데이터를 압축(리샘플링)합니다."""
    n = len(vals)
    if n <= width: return vals[:] # 데이터가 적으면 그대로 반환
    step = n / width; out = [vals[0]]
    for i in range(1, width):
        s = int(i * step); e = int((i + 1) * step); e = max(e, s + 1)
        if i == width - 1: e = n
        chunk = vals[s:e]
        if chunk: out.append(sum(chunk) / len(chunk)) # 구간의 평균값으로 압축
    return out

def render_chart(sym, days=180, width=None, height=None):
    """터미널에 텍스트 기반 차트를 그립니다."""
    U = ui()
    width = width or int(U.get("chart_width", 80)); height = height or int(U.get("chart_height", 15))
    
    bars, source_name = _get_chart_data(sym, days)
    if not bars: print(f"(차트 데이터 없음: {sym})"); return
    
    closes = [b["c"] for b in bars]; timestamps = [b["t"] for b in bars]
    vals = _resample(closes, width)
    
    lo, hi = min(vals), max(vals); span = (hi - lo) or 1e-9
    
    # Y축 (가격) 라벨 생성
    y_labels = [align_money_signed([hi - (span / (height - 1)) * i], decimals=2, show_plus=False)[0][0] for i in range(height)]
    y_label_width = max(len(s) for s in y_labels) if y_labels else 0
    
    # 차트 본문(grid) 생성
    grid = [[" " for _ in range(width)] for _ in range(height)]
    for x, v in enumerate(vals):
        y = int(((v - lo) / span) * (height - 1)); y = (height - 1) - y # 위가 높은 가격이 되도록 y축 뒤집기
        grid[y][x] = "█"
    
    col = up_down_color(vals[-1] - vals[0], U.get("color_scheme", "us"))
    sym_colored = color(sym.upper(), _sym_color(sym))
    
    # 차트 제목 출력
    top = f"=== {sym_colored}  {days}D Chart ({source_name}) {SEP} {dtfmt(now_et(), U.get('datetime_format','%m-%d-%y %H:%M:%S'))} ET"
    print(col(top))
    
    # Y축 라벨과 차트 본문 함께 출력
    for i in range(height):
        label = y_labels[i].rjust(y_label_width)
        print(f"{label} {col('│' + ''.join(grid[i]))}")
    
    # X축 (시간) 라벨 출력
    print(" " * y_label_width, col("└" + "─" * width))
    start_time_str = str(timestamps[0]).split("T")[0]; end_time_str = str(timestamps[-1]).split("T")[0]
    x_axis_label_line = list(start_time_str.ljust(width))
    x_axis_label_line[width-len(end_time_str):width] = list(end_time_str)
    print(" " * (y_label_width + 2) + "".join(x_axis_label_line))
    
    # 차트 요약 정보 출력
    avg = sum(vals)/len(vals)
    min_str, _ = align_money_signed([lo], show_plus=False); max_str, _ = align_money_signed([hi], show_plus=False); avg_str, _ = align_money_signed([avg], show_plus=False)
    print(f"Min: {min_str[0]} | Avg: {avg_str[0]} | Max: {max_str[0]}")