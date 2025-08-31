FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# 로그 및 데이터 디렉토리 생성
RUN mkdir -p /app/logs /app/data /app/config

EXPOSE 8888

CMD ["python", "backend/app.py"]