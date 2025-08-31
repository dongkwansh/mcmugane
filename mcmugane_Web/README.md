# Mcmugane Autotrader (Alpaca-first, Tabulated Terminal)

- FastAPI + WebSocket + tabulate 출력
- Synology DS923+ (Container Manager + Reverse Proxy) 배포용

## Quick Start (DSM Container Manager)
- `/volume1/docker/mcmugane`에 이 폴더 업로드/해제
- `configs/accounts.json`에 Alpaca 키 입력(페이퍼 권장)
- Projects → Local path = 이 폴더 → Start
- 브라우저: `http://NAS_IP:8000`
- 터미널: `HELP`, `FORMAT table|json`, `ACCOUNTS`, `ALGOS`, `POS`, `ORDERS`, `BARS`, `CANCELALL`

## Output
- 기본 출력은 **table** (tabulate/github 스타일), `FORMAT json`으로 변경 가능
