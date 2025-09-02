# app/terminal/formatter.py
from typing import List, Tuple
import unicodedata

def get_display_width(text: str) -> int:
    """문자열의 실제 표시 너비를 계산 (한글은 2, 영문은 1)"""
    width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ('F', 'W'):
            width += 2  # 한글, 전각 문자
        else:
            width += 1  # 영문, 반각 문자
    return width

def pad_to_width(text: str, width: int, align: str = 'left') -> str:
    """문자열을 지정된 너비로 패딩"""
    current_width = get_display_width(text)
    padding_needed = width - current_width
    
    if padding_needed <= 0:
        return text[:width]
    
    spaces = ' ' * padding_needed
    
    if align == 'left':
        return text + spaces
    elif align == 'right':
        return spaces + text
    elif align == 'center':
        left_pad = padding_needed // 2
        right_pad = padding_needed - left_pad
        return ' ' * left_pad + text + ' ' * right_pad
    
    return text

def format_table(headers: List[str], rows: List[List[str]], 
                 widths: List[int] = None, alignments: List[str] = None) -> str:
    """테이블 형식으로 데이터 포맷팅"""
    if not widths:
        # 자동으로 너비 계산
        widths = [max(get_display_width(h), 
                     max(get_display_width(str(row[i])) for row in rows) if rows else 0)
                  for i, h in enumerate(headers)]
    
    if not alignments:
        alignments = ['left'] * len(headers)
    
    # 헤더
    header_line = '│'.join(pad_to_width(h, w, a) 
                          for h, w, a in zip(headers, widths, alignments))
    
    # 구분선
    separator = '─' * sum(widths) + '─' * (len(headers) - 1) * 3
    
    # 데이터 행
    data_lines = []
    for row in rows:
        line = '│'.join(pad_to_width(str(cell), w, a) 
                       for cell, w, a in zip(row, widths, alignments))
        data_lines.append(line)
    
    # 조합
    result = [
        '┌' + separator + '┐',
        '│' + header_line + '│',
        '├' + separator + '┤',
    ]
    
    for line in data_lines:
        result.append('│' + line + '│')
    
    result.append('└' + separator + '┘')
    
    return '\n'.join(result)

def format_status_box(title: str, items: List[Tuple[str, str]], width: int = 60) -> str:
    """상태 정보를 박스 형식으로 포맷팅"""
    lines = []
    separator = '═' * (width - 2)
    
    lines.append('╔' + separator + '╗')
    lines.append('║' + pad_to_width(title, width - 2, 'center') + '║')
    lines.append('╠' + separator + '╣')
    
    for label, value in items:
        label_width = 20
        value_width = width - label_width - 5
        
        formatted_line = (
            pad_to_width(label, label_width, 'left') + 
            ' : ' + 
            pad_to_width(str(value), value_width, 'left')
        )
        lines.append('║' + formatted_line + '║')
    
    lines.append('╚' + separator + '╝')
    
    return '\n'.join(lines)