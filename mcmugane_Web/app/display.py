from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
from tabulate import tabulate
import orjson

class DisplayManager:
    def __init__(self):
        self._fmt: Dict[str, str] = {}  # conn_id -> 'table' | 'json'

    def set_format(self, conn_id: str, fmt: str):
        fmt = (fmt or "table").lower()
        if fmt not in ("table", "json"):
            fmt = "table"
        self._fmt[conn_id] = fmt

    def get_format(self, conn_id: str) -> str:
        return self._fmt.get(conn_id, "table")

    def render(self, conn_id: str, rows: Union[Dict[str, Any], List[Any], Any],
               headers: Optional[List[str]] = None, tablefmt: str = "github") -> str:
        fmt = self.get_format(conn_id)
        if fmt == "json":
            return orjson.dumps(rows, option=orjson.OPT_INDENT_2).decode()

        # dict -> key/value 표
        if isinstance(rows, dict):
            items = [{"key": str(k), "value": rows[k]} for k in rows.keys()]
            keys = headers or ["key", "value"]
            data = [[it.get(k, "") for k in keys] for it in items]
            return tabulate(data, headers=keys, tablefmt=tablefmt, stralign="right", numalign="right")

        # list[dict] -> 유니온 헤더
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            keys = headers or sorted({k for r in rows for k in r.keys()})
            data = [[("" if r.get(k) is None else r.get(k, "")) for k in keys] for r in rows]
            return tabulate(data, headers=keys, tablefmt=tablefmt, stralign="right", numalign="right")

        # list[...] 또는 기타
        if isinstance(rows, list):
            return tabulate(rows, headers=headers, tablefmt=tablefmt, stralign="right", numalign="right")

        return str(rows)

display = DisplayManager()
