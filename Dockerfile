# Wealth Commander Dockerfile
# 한글 주석: Synology Container Manager에서 바로 빌드/실행 가능하도록 설계되었습니다.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_DISABLE_PIP_VERSION_CHECK=1     PIP_NO_CACHE_DIR=1

# 시스템 패키지 (필요 최소한)
RUN apt-get update && apt-get install -y --no-install-recommends     build-essential curl tzdata     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 요구 패키지 설치
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# 앱 복사
COPY app /app/app
COPY .env /app/.env || true

# 네트워크 포트
EXPOSE 8000

# Healthcheck (간단)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
