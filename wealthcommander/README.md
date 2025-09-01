# WealthCommander Trading System v1.0

Alpaca API를 활용한 자동/수동 주식 매매 시스템

## 기능

- 📊 실시간 포트폴리오 관리
- 🤖 자동매매 전략 실행
- 💻 터미널 기반 수동 매매
- 📈 다양한 매매 전략 지원
- 🔒 여러 Paper/Live 계좌 지원 및 전환

## 설치 방법

### 1. 환경 설정
프로젝트 최상위 경로에 `.env` 파일을 생성하고 아래 형식에 맞게 Alpaca API 키와 설정을 입력합니다.

```bash
# Live Account
ALPACA_LIVE_KEY_ID=AK...
ALPACA_LIVE_SECRET_KEY=...

# Paper Account 1 (Default)
ALPACA_PAPER1_KEY_ID=PK...
ALPACA_PAPER1_SECRET_KEY=...

# Paper Account 2
ALPACA_PAPER2_KEY_ID=PK...
ALPACA_PAPER2_SECRET_KEY=...

# Paper Account 3
ALPACA_PAPER3_KEY_ID=PK...
ALPACA_PAPER3_SECRET_KEY=...

# 앱 실행 시 기본으로 선택될 계좌 (LIVE, PAPER1, PAPER2, PAPER3 중 하나)
DEFAULT_ACCOUNT=PAPER1

# App Settings
APP_ENV=production
TZ=Asia/Seoul