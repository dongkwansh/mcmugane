FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 업데이트
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 전체 app 폴더 복사 (static 포함)
COPY app ./

# config 폴더 복사
COPY config ./config

# logs 디렉토리 생성
RUN mkdir -p logs

EXPOSE 8080

# main.py가 /app 폴더 직접 아래에 있으므로
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]