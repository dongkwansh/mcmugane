# WealthCommander Synology 923+ 설치 가이드

이 가이드는 WealthCommander 트레이딩 애플리케이션을 Synology 923+ NAS의 Container Manager를 통해 설치하는 방법을 설명합니다.

## 사전 요구사항

### 하드웨어
- Synology 923+ NAS (또는 호환 모델)
- 최소 2GB RAM (4GB 권장)
- 최소 10GB 저장 공간

### 소프트웨어
- DSM 7.0 이상
- Container Manager 패키지 설치됨
- SSH 액세스 (선택사항, 고급 설정용)

### API 키 준비
- Alpaca Markets 계정 및 API 키 (https://alpaca.markets)
- Paper Trading API 키 (테스트용)
- Live Trading API 키 (실거래용, 선택사항)

## 설치 단계

### 1단계: 프로젝트 파일 준비

1. 이 프로젝트의 zip 파일을 Synology NAS에 업로드
2. File Station을 통해 적절한 위치에 압축 해제 (예: `/docker/wealthcommander/`)

### 2단계: Container Manager 설정

1. **Container Manager** 패키지를 열기
2. **프로젝트** 탭으로 이동
3. **새로 만들기** 클릭

### 3단계: Docker Compose 설정

1. **프로젝트 이름**: `wealthcommander`
2. **소스**: **기존 docker-compose.yml 파일 업로드** 선택
3. 압축 해제한 폴더에서 `docker-compose.yml` 파일 선택

### 4단계: 환경 변수 설정

Container Manager에서 환경 변수를 설정합니다:

```bash
# 기본 설정
NODE_ENV=production
PORT=8080
TZ=Asia/Seoul

# Alpaca API 키 설정 (실제 값으로 변경)
ALPACA_LIVE_API_KEY=your_live_api_key_here
ALPACA_LIVE_SECRET_KEY=your_live_secret_key_here

ALPACA_PAPER_API_KEY_1=your_paper_api_key_1_here
ALPACA_PAPER_SECRET_KEY_1=your_paper_secret_key_1_here

ALPACA_PAPER_API_KEY_2=your_paper_api_key_2_here
ALPACA_PAPER_SECRET_KEY_2=your_paper_secret_key_2_here

ALPACA_PAPER_API_KEY_3=your_paper_api_key_3_here
ALPACA_PAPER_SECRET_KEY_3=your_paper_secret_key_3_here
```

### 5단계: 네트워크 및 포트 설정

1. **포트 설정**: 8080 포트가 외부에서 접근 가능하도록 설정
2. **방화벽**: DSM 제어판 > 보안 > 방화벽에서 8080 포트 허용

### 6단계: 컨테이너 시작

1. **다음** 클릭하여 설정 완료
2. **시작** 클릭하여 컨테이너 실행

## 접속 방법

### 웹 브라우저 접속
```
http://[NAS IP주소]:8080
```

### 기본 로그인 정보
- **관리자**: 
  - ID: `admin`
  - 비밀번호: `Mcmugane1234`
  - 권한: 모든 계정 접근 가능

- **게스트**: 
  - ID: `guest`
  - 비밀번호: `Guest4321`
  - 권한: paper-account-3만 접근 가능

## 모니터링 및 관리

### 컨테이너 상태 확인
1. Container Manager > 컨테이너 탭
2. `wealthcommander-app` 컨테이너 상태 확인
3. 로그 탭에서 애플리케이션 로그 확인

### 데이터 백업
중요한 데이터는 다음 위치에 저장됩니다:
- `/app/logs` - 거래 로그 및 시스템 로그
- `/app/data` - 전략 설정 및 사용자 데이터

### 업데이트 방법
1. 새 버전의 Docker 이미지 다운로드
2. Container Manager에서 컨테이너 중지
3. 새 이미지로 컨테이너 재시작

## 보안 설정

### 네트워크 보안
- VPN 또는 방화벽을 통한 접근 제한 권장
- HTTPS 리버스 프록시 설정 (선택사항)

### API 키 보안
- API 키는 환경 변수로만 설정
- Paper Trading 키로 먼저 테스트
- Live Trading 사용 시 주의사항 숙지

## 문제 해결

### 일반적인 문제

1. **컨테이너가 시작되지 않음**
   - 포트 충돌 확인 (8080 포트 사용 여부)
   - 로그에서 오류 메시지 확인
   - 환경 변수 설정 재확인

2. **API 연결 오류**
   - Alpaca API 키 유효성 확인
   - 네트워크 연결 상태 확인
   - 방화벽 설정 확인

3. **성능 문제**
   - Container Manager에서 리소스 사용량 확인
   - 메모리 부족 시 RAM 증설 고려

### 로그 확인 방법
```bash
# SSH를 통한 로그 확인 (고급 사용자)
docker logs wealthcommander-app
```

## 지원 및 문의

- 애플리케이션 관련 문의: GitHub Issues
- Synology 관련 문의: Synology 고객 지원
- API 관련 문의: Alpaca Markets 지원팀

## 라이선스 및 면책사항

- 이 소프트웨어는 교육 및 연구 목적으로 제공됩니다
- 실거래 시 발생하는 손실에 대해 개발자는 책임지지 않습니다
- API 키 보안은 사용자의 책임입니다

---

## 추가 팁

1. **정기 백업**: 중요한 전략 설정과 로그는 정기적으로 백업
2. **모니터링**: 시스템 리소스 사용량을 정기적으로 모니터링
3. **업데이트**: 보안 업데이트는 즉시 적용 권장
4. **테스트**: 새로운 전략은 Paper Trading으로 먼저 테스트