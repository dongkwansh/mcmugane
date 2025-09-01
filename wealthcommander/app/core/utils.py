# app/core/utils.py
import math

def compute_qty_from_budget(price: float, budget: float, fractional: bool) -> float:
    """예산과 가격을 기반으로 주식 수량을 계산합니다."""
    if price <= 0:
        return 0
    qty = budget / price
    # 소수점 거래가 가능하면 소수점 2자리까지, 아니면 정수로 내림합니다.
    return math.floor(qty * 100) / 100.0 if fractional else math.floor(qty)

def format_number(value: float, decimals: int = 2) -> str:
    """숫자를 쉼표가 포함된 문자열로 포맷팅합니다."""
    return f"{value:,.{decimals}f}"

def format_order(order) -> str:
    """Alpaca 주문 객체를 읽기 쉬운 문자열로 변환합니다."""
    return (f"ID: {order.id[:8]}... | {order.symbol} {order.side.upper()} {order.qty}주 | "
            f"타입: {order.order_type.upper()} | 상태: {order.status.upper()}")

def format_position(position) -> str:
    """Alpaca 포지션 객체를 읽기 쉬운 문자열로 변환합니다."""
    market_value = float(position.market_value)
    cost_basis = float(position.cost_basis)
    pnl = market_value - cost_basis
    pnl_pct = (pnl / cost_basis * 100) if cost_basis != 0 else 0
    
    return (f"{position.symbol:<8} | 수량: {position.qty:<10} | "
            f"평단가: ${format_number(float(position.avg_entry_price))} | "
            f"현재가치: ${format_number(market_value)} | "
            f"손익: ${format_number(pnl)} ({pnl_pct:+.2f}%)")