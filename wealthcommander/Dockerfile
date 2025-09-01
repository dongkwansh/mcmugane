FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# app 폴더 전체 복사 (static, strategies, terminal 포함)
COPY app ./app

# config 폴더 복사
COPY config ./config

# logs 디렉토리 생성
RUN mkdir -p logs

EXPOSE 8080

# app.main:app 경로로 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]