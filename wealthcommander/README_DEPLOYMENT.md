# 🚀 WealthCommander - Synology Container Manager 배포 가이드

## 📋 시스템 요구사항

- **Synology NAS**: DSM 7.x 이상 (923+ 또는 호환 모델)
- **Container Manager**: 패키지 센터에서 설치
- **메모리**: 최소 1GB RAM 권장
- **저장공간**: 최소 2GB 사용 가능 공간
- **포트**: 8080 (설정 가능)
- **Alpaca Trading Account**: API 인증 정보 (옵션)

## 🐳 배포 단계

### 1단계: 프로젝트 파일 준비

1. **File Station**에서 폴더 생성:
   ```
   /docker/wealthcommander/
   ```

2. 모든 프로젝트 파일을 이 폴더에 업로드

### 2단계: Container Manager 설정

1. **Container Manager** → **프로젝트** → **새로 만들기**
2. 프로젝트명: `wealthcommander`
3. 경로: `/docker/wealthcommander`
4. 소스: `docker-compose.yml` 파일 선택

### 3단계: 환경 변수 설정 (옵션)

Container Manager에서 다음 환경 변수를 설정하세요:

```env
# 🔑 Alpaca API 인증 정보 (실제 거래용)
ALPACA_LIVE_API_KEY=실제_라이브_API_키
ALPACA_LIVE_SECRET_KEY=실제_라이브_비밀키
ALPACA_PAPER_API_KEY_1=페이퍼_API_키_1
ALPACA_PAPER_SECRET_KEY_1=페이퍼_비밀키_1
ALPACA_PAPER_API_KEY_2=페이퍼_API_키_2
ALPACA_PAPER_SECRET_KEY_2=페이퍼_비밀키_2
ALPACA_PAPER_API_KEY_3=페이퍼_API_키_3
ALPACA_PAPER_SECRET_KEY_3=페이퍼_비밀키_3

# 🌏 시스템 설정
NODE_ENV=production
PORT=8080
TZ=Asia/Seoul
```

### 4단계: 컨테이너 빌드 및 시작

1. **빌드** 버튼 클릭 (첫 빌드는 5-10분 소요)
2. 빌드 로그를 모니터링하여 진행 상황 확인
3. 빌드 완료 후 **시작** 버튼 클릭
4. 컨테이너 상태가 "실행 중"이 될 때까지 대기

### 5단계: 접속 확인

브라우저에서 `http://시놀로지_IP:8080`로 접속

## 👥 기본 사용자 계정

| 계정 | 비밀번호 | 권한 |
|------|----------|------|
| `admin` | `Mcmugane1234` | 모든 계정 접근 |
| `guest` | `Guest4321` | Paper Account 3만 접근 |

## 🎯 주요 기능

### ✅ 완료된 기능들
- ✅ **터미널 레이아웃 최적화** - 공백 제거 및 UI 개선
- ✅ **실시간 자동매매 상태 표시** - WebSocket 기반
- ✅ **전략 정보 JSON 디스플레이** - 상세 매개변수 표시
- ✅ **역할 기반 접근 제어** - admin/guest 권한 분리
- ✅ **JSONL 거래 로깅** - 감사 추적 가능
- ✅ **bcrypt 보안 인증** - 안전한 비밀번호 저장
- ✅ **WebSocket 실시간 통신** - 즉시 업데이트
- ✅ **전문가급 옵션 전략** - Iron Condor, Covered Call, Bull Put Spread
- ✅ **한국어 전략 설명** - 모든 매개변수 한국어 주석
- ✅ **Docker 프로덕션 최적화** - 멀티스테이지 빌드

### 🛡️ 보안 기능
- Non-root 사용자로 실행
- 메모리 및 CPU 제한 (1GB RAM, 1 CPU 코어)
- Health check 자동 모니터링 (30초 간격)
- 보안 옵션 활성화
- 최소 권한 원칙 적용

## 📊 모니터링 및 관리

### 컨테이너 상태 확인
Container Manager → 컨테이너 → wealthcommander-app

### 로그 확인
Container Manager → 컨테이너 → wealthcommander-app → 세부 정보 → 로그

### Health Check
시스템이 자동으로 30초마다 상태 확인:
- API 엔드포인트 가용성 (`/api/status`)
- 시스템 리소스 사용량
- 거래 시스템 상태

## 📁 중요한 디렉토리 구조

```
/docker/wealthcommander/
├── data/                    # 설정 및 전략 데이터
│   ├── strategies.json      # 거래 전략 설정
│   ├── users.json          # 사용자 계정 정보
│   ├── messages.json       # 시스템 메시지
│   └── myETF.json          # ETF 그룹 설정
├── logs/                   # 로그 파일
│   ├── logins/            # 로그인 기록 (JSONL)
│   └── statements/        # 거래 내역 (JSONL)
├── Dockerfile             # Docker 빌드 설정
├── docker-compose.yml     # 컨테이너 오케스트레이션
└── README_DEPLOYMENT.md   # 이 가이드 파일
```

## 🔧 문제 해결

### 컨테이너가 시작되지 않는 경우
1. **환경 변수 확인**: 모든 필수 변수가 올바르게 설정되었는지 확인
2. **API 인증 정보**: Alpaca API 키가 유효한지 확인
3. **시스템 리소스**: RAM/CPU 사용량 확인
4. **포트 충돌**: 8080 포트가 다른 서비스에서 사용 중인지 확인

### 웹 인터페이스 접속 불가
1. **방화벽 설정**: DSM 제어판 → 보안 → 방화벽에서 8080 포트 허용
2. **컨테이너 상태**: Container Manager에서 실행 상태 확인
3. **로그 확인**: 컨테이너 로그에서 오류 메시지 확인
4. **네트워크**: 같은 네트워크에서 접속하고 있는지 확인

### 거래 관련 문제
1. **API 인증**: Alpaca API 키의 유효성 및 권한 확인
2. **시장 시간**: 미국 주식 시장 개장 시간 확인
3. **계정 상태**: 거래 가능한 계정 상태인지 확인
4. **로그 검토**: 애플리케이션 내 거래 로그 확인

### 성능 최적화
```yaml
# docker-compose.yml에서 리소스 조정 가능
deploy:
  resources:
    limits:
      memory: 2G        # 필요시 증가
      cpus: '2.0'       # 필요시 증가
```

## 🔒 보안 수칙

1. **즉시 기본 비밀번호 변경** - 보안을 위해 필수
2. **HTTPS 설정** - DSM 역방향 프록시 사용
3. **정기적인 백업** - 중요 데이터 보호
4. **로그 모니터링** - 의심스러운 활동 추적
5. **API 키 관리** - 최소 권한으로 설정
6. **방화벽 설정** - 불필요한 포트 차단

## 📦 빌드 과정

이 패키지는 다음 과정을 거쳐 최적화됩니다:

1. **Frontend 빌드**: React + TypeScript + Vite
2. **Backend 컴파일**: Node.js + TypeScript + esbuild
3. **Multi-stage Docker**: 경량화된 Alpine Linux 기반
4. **프로덕션 최적화**: 불필요한 파일 제거 및 보안 강화

## 📞 지원

문제 발생 시 확인사항:
1. Container Manager 로그에서 오류 메시지 확인
2. 모든 환경 변수가 올바르게 설정되었는지 확인
3. Alpaca API 인증 정보의 적절한 권한 확인
4. 시스템 리소스 사용량 모니터링

---

**⚠️ 면책 조항**: 이 소프트웨어는 교육 목적입니다. 실제 자금 사용 전 반드시 페이퍼 트레이딩으로 테스트하세요. 거래에는 손실 위험이 있습니다.