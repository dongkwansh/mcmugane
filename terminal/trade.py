# trade.py
# buy, sell, cancel 등 모든 거래 관련 로직을 처리하는 파일입니다.
# CLI(명령줄) 주문과 대화형(interactive) 주문 흐름을 모두 관리합니다.

from config import baskets as cfg_baskets
from api import alp_place_order, alp_orders_open, alp_order_cancel_all, alp_order_cancel, alp_acct, stooq_light, alp_asset, alp_positions
from core import safe_float, safe_int, align_int_commas, align_money_signed
from ui_colors import color, colorize_delta_money
from view_list import _sym_color
import re

# --- 유틸리티 함수 ---

def _parse_qty_token(tok):
    """사용자가 입력한 수량/금액 토큰을 파싱하여 종류와 값으로 변환합니다. (예: '10', '$150.5', 'all')"""
    tok=(tok or "").strip().lower()
    if not tok: return ("missing", None)
    cleaned_tok = re.sub(r'[$,]', '', tok)
    if tok.endswith("%"):
        try: return ("pct", float(cleaned_tok[:-1]))
        except: return ("pct", None)
    if tok.startswith("$"):
        try: return ("notional", float(cleaned_tok))
        except: return ("notional", None)
    if tok=="all": return ("all", None)
    try: return ("qty", float(cleaned_tok))
    except ValueError:
        try: return("notional", float(cleaned_tok))
        except ValueError: return ("unknown", None)

def _check_asset_tradable(sym):
    """주문 전, 종목이 거래 가능한 상태인지 Alpaca API를 통해 확인합니다."""
    asset_info = alp_asset(sym)
    if not asset_info or "_error" in asset_info: raise RuntimeError(f"{sym} 종목 정보를 조회할 수 없습니다.")
    if not asset_info.get("tradable"): raise RuntimeError(f"{sym} 종목은 현재 거래가 불가능합니다 (상태: {asset_info.get('status')}).")

def _pre_trade_check(sym, side, kind, val, limit):
    """매수 주문 전, 계좌의 매수 가능 금액이 충분한지 확인합니다."""
    if side != "buy": return True, ""
    try:
        acct = alp_acct()
        if "_error" in acct: raise RuntimeError(f"계좌 정보 조회 실패: {acct['_error']}")
        buying_power = safe_float(acct.get("buying_power", 0))
        est_cost = 0
        if kind == "qty":
            qty = safe_float(val)
            price = safe_float(limit)
            if price == 0: # 시장가 주문
                quote = stooq_light(sym)
                if not quote: raise RuntimeError(f"{sym} 현재가 조회 실패")
                price = safe_float(quote.get("Close"))
            est_cost = qty * price
        elif kind == "notional": est_cost = safe_float(val)
        else: return True, ""
        if est_cost > buying_power:
            msg = f"주문 거부: 매수 가능 금액 부족 (주문액: ${est_cost:,.2f}, 가능액: ${buying_power:,.2f})"
            raise RuntimeError(msg)
        return True, ""
    except Exception as e: return False, str(e)

# --- 주문 실행 함수 ---

def _place_by_kind(sym, side, kind, val, limit):
    """파싱된 주문 정보를 바탕으로 실제 주문을 Alpaca API로 전송합니다."""
    ok, reason = _pre_trade_check(sym, side, kind, val, limit)
    if not ok: raise RuntimeError(reason)
    if kind=="qty":
        if val is None or float(val)<=0: raise RuntimeError("수량이 올바르지 않습니다.")
        return alp_place_order(sym, qty=float(val), side=side, type_=("limit" if limit is not None else "market"), limit_price=limit)
    if kind=="notional":
        if val is None or float(val)<=0: raise RuntimeError("금액이 올바르지 않습니다.")
        return alp_place_order(sym, side=side, type_=("limit" if limit is not None else "market"), limit_price=limit, notional=float(val))
    if kind=="pct": raise RuntimeError("퍼센트 주문은 현재 Notional($)로만 지원됩니다. 예: $100")
    if kind=="all":
        if side=="sell": return alp_place_order(sym, side="sell", type_="market", qty="100%")
        raise RuntimeError("'all'은 매도 주문에서만 사용할 수 있습니다.")
    raise RuntimeError("수량/금액 형식을 해석할 수 없습니다.")

def _execute_sell_flow(sym):
    """선택된 종목에 대한 매도 절차(수량/가격 입력)를 진행합니다."""
    try:
        tok = input(f"[{sym}] 판매할 수량/금액? (예: 10 | $100 | all): ").strip()
        lim_str = (input(f"[{sym}] 리밋가? (비우면 market): ").strip() or None)
        kind, val = _parse_qty_token(tok)
        limit = float(re.sub(r'[$,]', '', lim_str)) if lim_str else None
        
        result = _place_by_kind(sym, "sell", kind, val, limit)
        print(color("요청 전송 완료.", "green"))
        print(f"  - 종목: {result.get('symbol')}, 수량: {result.get('qty')}, 상태: {result.get('status')}")
    except (RuntimeError, ValueError) as e:
        print(color(f"[오류] {e}", "bright_red"))

# --- CLI 명령어 처리 함수 ---

def buy_cli(sym, qty_tok, price_tok):
    """buy .TICKER QTY [PRICE] 형식의 CLI 명령어를 처리합니다."""
    try:
        _check_asset_tradable(sym)
        kind, val = _parse_qty_token(qty_tok)
        limit = None
        if kind == "missing":
            tok = input(f"수량/금액? (예: 10 | $100 ): ").strip(); kind, val = _parse_qty_token(tok)
        if price_tok: limit = float(re.sub(r'[$,]', '', price_tok))
        elif kind != "notional":
            lim_str = input(f"리밋가? (비우면 market): ").strip()
            if lim_str: limit = float(re.sub(r'[$,]', '', lim_str))
        result = _place_by_kind(sym, "buy", kind, val, limit)
        print(color("요청 전송 완료.", "green")); print(f"  - 종목: {result.get('symbol')}, 수량: {result.get('qty')}, 상태: {result.get('status')}")
    except (RuntimeError, ValueError) as e: print(color(f"[오류] {e}", "bright_red"))

def sell_cli(sym, qty_tok, price_tok):
    """sell .TICKER QTY [PRICE] 형식의 CLI 명령어를 처리합니다."""
    try:
        _check_asset_tradable(sym)
        kind, val = _parse_qty_token(qty_tok)
        limit = None
        if kind == "missing":
            tok = input(f"수량/금액? (예: 10 | $100 | all): ").strip(); kind, val = _parse_qty_token(tok)
        if price_tok: limit = float(re.sub(r'[$,]', '', price_tok))
        elif kind not in ["notional", "all"]:
             lim_str = input(f"리밋가? (비우면 market): ").strip()
             if lim_str: limit = float(re.sub(r'[$,]', '', lim_str))
        result = _place_by_kind(sym, "sell", kind, val, limit)
        print(color("요청 전송 완료.", "green")); print(f"  - 종목: {result.get('symbol')}, 수량: {result.get('qty')}, 상태: {result.get('status')}")
    except (RuntimeError, ValueError) as e: print(color(f"[오류] {e}", "bright_red"))

# --- 대화형 명령어 처리 함수 ---

def buy_interactive():
    """'buy' 대화형 명령어를 처리합니다."""
    try:
        tgt=input("매수할 대상? (.TICKER | BasketName): ").strip()
        if not tgt: raise ValueError("대상이 비었습니다.")
        if tgt.startswith("."):
            sym=tgt[1:].upper(); _check_asset_tradable(sym)
            tok=input(f"수량/금액? (예: 10 | $100): ").strip()
            lim_str=(input("리밋가? (비우면 market): ").strip() or None)
            kind,val=_parse_qty_token(tok)
            limit = float(re.sub(r'[$,]', '', lim_str)) if lim_str else None
            result = _place_by_kind(sym, "buy", kind, val, limit)
            print(color("요청 전송 완료.", "green")); print(f"  - 종목: {result.get('symbol')}, 수량: {result.get('qty')}, 상태: {result.get('status')}")
            return
        bks=cfg_baskets()
        if tgt not in bks: raise ValueError(f"사용자 바스켓 '{tgt}' 이(가) 없습니다.")
        print("(미구현) 바스켓 일괄 주문은 추후 지원 예정.")
    except (RuntimeError, ValueError) as e: print(color(f"[오류] {e}", "bright_red"))

def sell_interactive():
    """[대대적 기능 개선] 'sell' 대화형 명령어를 처리합니다."""
    try:
        positions = alp_positions()
        if isinstance(positions, dict) and "_error" in positions:
            raise RuntimeError(f"포지션 조회 실패: {positions['_error']}")
        if not positions:
            print("(판매할 보유 종목이 없습니다.)"); return

        # --- 보유 종목 상세 정보 조회 및 계산 ---
        print("현재가 조회 중...")
        pos_details = []
        for i, p in enumerate(positions):
            sym = p.get("symbol")
            qty = safe_float(p.get("qty"))
            avg_price = safe_float(p.get("avg_entry_price"))
            
            quote = stooq_light(sym)
            current_price = safe_float(quote.get("Close")) if quote else 0
            
            cost_basis = qty * avg_price
            market_value = qty * current_price
            unrealized_pl = market_value - cost_basis
            unrealized_pl_pct = (unrealized_pl / cost_basis * 100.0) if cost_basis else 0.0
            
            pos_details.append({
                "idx": i + 1, "sym": sym, "qty": qty, "avg_price": avg_price,
                "current_price": current_price, "pl": unrealized_pl, "pl_pct": unrealized_pl_pct
            })

        # --- 정렬된 표(테이블) 생성 ---
        qty_s, w_qty = align_int_commas([p['qty'] for p in pos_details])
        avg_s, w_avg = align_money_signed([p['avg_price'] for p in pos_details])
        cur_s, w_cur = align_money_signed([p['current_price'] for p in pos_details])
        
        header = ["#", "Sym.", "Qty", "AvgPrice", "CurPrice", "Unrealized P/L"]
        print(" ".join([h.ljust(w) for h, w in zip(header, [3, 7, w_qty, w_avg, w_cur, 20])]))
        
        for i, p in enumerate(pos_details):
            idx_str = f"{(str(i+1)+'.').ljust(3)}"
            sym_str = color(f"{p['sym']:<7}", _sym_color(p['sym']))
            pl_str = colorize_delta_money(p['pl'], p['pl_pct'])
            
            print(f"{idx_str}{sym_str}{qty_s[i]} {avg_s[i]} {cur_s[i]} {pl_str}")

        # --- 사용자 선택 처리 ---
        selection = input("판매할 종목의 번호 또는 티커를 입력하세요 (취소: Enter): ").strip()
        if not selection:
            print("매도를 취소했습니다."); return

        selected_pos = None
        if selection.isdigit(): # 번호로 선택
            idx = int(selection)
            if 1 <= idx <= len(pos_details):
                selected_pos = pos_details[idx-1]
        else: # 티커로 선택
            for p in pos_details:
                if p['sym'].lower() == selection.lower():
                    selected_pos = p; break
        
        if not selected_pos:
            print(color("잘못된 선택입니다.", "bright_red")); return
        
        # 선택된 종목으로 매도 절차 진행
        _execute_sell_flow(selected_pos['sym'])

    except (RuntimeError, ValueError) as e:
        print(color(f"[오류] {e}", "bright_red"))

def cancel_interactive(order_id=None):
    """'cancel' 대화형 명령어를 처리합니다."""
    try:
        if order_id:
            alp_order_cancel(order_id); print(f"주문({order_id[:7]}...) 취소 요청 완료."); return
        od=alp_orders_open()
        if isinstance(od,dict) and od.get("_error"): raise RuntimeError(f"열린 주문 조회 실패: {od['_error']}")
        if not od: print("(열린 주문 없음)"); return
        print("--- 열린 주문 목록 ---")
        for i,o in enumerate(od, start=1):
            sym_colored = color(f"{o.get('symbol', ''):<6}", _sym_color(o.get('symbol', '')))
            side = o.get('side', '').ljust(4); qty = str(o.get('qty', '')).rjust(5)
            type_ = o.get('type', '').ljust(8)
            limit = f" @ ${o.get('limit_price', '-')}" if o.get('type') == 'limit' else ''
            print(f"{str(i).rjust(2)}: {sym_colored} {side} {qty} {type_}{limit}")
        print("--------------------")
        sel=input("취소 번호(엔터=취소, all=전체): ").strip().lower()
        if sel=="all": cancel_all_orders()
        elif sel:
            i=int(sel)-1; oid=od[i].get("id")
            alp_order_cancel(oid); print(f"주문({oid[:7]}...) 취소 요청 완료.")
        else: print("취소 안 함.")
    except (RuntimeError, ValueError, IndexError) as e: print(color(f"[오류] {e}", "bright_red"))

def cancel_all_orders():
    """모든 열린 주문을 취소합니다."""
    try:
        alp_order_cancel_all()
        print("모든 열린 주문에 대한 전체 취소 요청을 완료했습니다.")
    except (RuntimeError, ValueError) as e:
        print(color(f"[오류] {e}", "bright_red"))