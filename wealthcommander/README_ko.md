# Wealth Commander (웹 대시보드 + 터미널) 🇰🇷

**자동 매매 / 수동 매매 / 백테스트(향후) 통합 주식 관리 도구**  
Synology 923+ 의 Container Manager(Docker)에서 테스트/운영하도록 구성했습니다.  
거래 계좌는 Alpaca API를 사용합니다.

> ⚠️ 보안: 본 레포에는 `.env`가 포함되어 있지만, 실계좌 운용 전에는 반드시 각 계정의 올바른 키로 교체하세요.

---

## 📦 설치 (Synology 또는 로컬)
1. 압축 해제 경로 예시: `/volume1/docker/wealthcommander/`
2. 폴더 진입 후 컨테이너 빌드/실행
   ```bash
   docker compose up -d --build
   ```
3. 접속: <http://YOUR_SYNOLOGY_IP:8000>

- **데이터 지속성**: `app/data`(전략/myETF)와 `app/logs`는 볼륨 마운트되어 컨테이너 재시작에도 보존됩니다.
- **시간대**: `.env`의 `TZ`로 제어 (기본 `America/New_York`).

---

## 🧩 주요 기능
- **4열 레이아웃 대시보드**
  - (좌1열 상) **계좌 선택/정보 카드**: 계좌 선택, 정보(Buying Power/Equity 등), 뉴욕시장(NY) 시간, Extended Hours 토글/인디케이터, **Reload JSON** 버튼
  - (좌1열 하) **자동매매 카드**: 계정 전용 전략 JSON 목록(live/paperX prefix 필터), 시작/중지, 상태 인디케이터, 최근 5줄 상황판
  - (우3열) **터미널 + 시스템 메시지 + 명령 입력창**: Up/Down 으로 최근 명령 10개 히스토리
- **터미널 명령어 (한글 인터랙션)**
  - `buy/sell/orders/history/cancel/.(TICKER)`
  - `.TICKER`: 현재가/전일 O/H/L/Close, 보유 여부/수량/평단 등
  - `buy` 대화형 또는 인자 사용:
    - `buy .SOXL` → 수량/금액/비율, 목표가 입력 → 확인(Y/N)
    - `buy .SOXL 20` → 20주
    - `buy .SOXL 20%` → Buying Power 20%
    - `buy .SOXL $20` → 20달러어치
    - `buy .SOXL $20 10` → 10달러 목표가로 2주(예) 계산
    - `buy myTECH_01 $1000` → myETF 비중대로 배분
  - `sell`/`cancel`도 유사 인터페이스
- **전략/포트폴리오**
  - `auto_methods/*.json`: 계정 prefix(`live_`, `paper1_` 등)별로 **가장 활용도 높은 5가지 전략** 템플릿 제공
  - `myETF/*.json`: 사용자가 정의한 종목 바스켓(비중 합 100% 필수, 아니면 경고 및 거래 비활성)

---

## 🔑 Alpaca 연동
- `.env`에 계정별 키/시크릿을 설정합니다.
- 기본은 **Paper#1 키를 모든 계정에 동일 적용**하여 바로 테스트 가능하도록 했습니다.
- 트레이딩: `https://paper-api.alpaca.markets/v2` 또는 `https://api.alpaca.markets/v2`
- 시세(Data): `https://data.alpaca.markets/v2` (기본 feed: `iex`)

> 문서: Alpaca 공식 문서(인증/주문/시세) 참고.

---

## 🗂 디렉토리
```
app/
  main.py                # FastAPI 앱 진입
  config.py              # 환경설정 로더
  trading/
    alpaca_client.py     # Alpaca REST 래퍼 (주문/계좌/시세)
    order_utils.py       # 수량/금액/비율 계산 유틸
    indicators.py        # SMA/RSI/ATR 지표
    strategies.py        # 5가지 전략 엔진
    autobot.py           # 자동매매 루프/상태 관리
  templates/
    index.html           # 웹 UI (4열 대시보드)
  static/
    main.js              # 프론트 동작/웹소켓/명령히스토리
    styles.css           # 간단한 스타일
  data/
    auto_methods/        # 계정별 전략 JSON
    myETF/               # 사용자 myETF JSON
  logs/
    app.log
```

---

## ▶️ 실행 팁
- UI 좌상단 카드의 **Reload JSON** 버튼으로 `auto_methods`/`myETF`를 즉시 다시 불러옵니다.
- **Extended Hours** 토글이 켜져 있어야 프리마켓/애프터마켓 주문에 `extended_hours=true`로 제출됩니다.
- **myETF**의 비중 합이 100이 아니면 경고가 뜨고, 해당 myETF 거래가 비활성화됩니다.

---

## ⚠️ 면책
- 본 예제는 교육/연구용입니다. 실거래 전, 전략 검증/리스크 관리/오류 핸들링을 충분히 수행하세요.
