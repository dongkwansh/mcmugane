# WealthCommander - Optimized for Synology NAS 923+
# Multi-stage build for minimal container size

# Build stage
FROM python:3.11-slim as builder

# Set environment variables for container optimization
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Synology NAS optimizations
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    TZ=America/New_York \
    WORKER_TIMEOUT=120 \
    MAX_WORKERS=1 \
    PORT=8080

# Create non-root user for security
RUN groupadd -r wealthcommander && \
    useradd -r -g wealthcommander -d /app -s /sbin/nologin wealthcommander

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create application directories
WORKDIR /app
RUN mkdir -p /app/logs /app/config /app/static && \
    chown -R wealthcommander:wealthcommander /app

# Copy application code
COPY --chown=wealthcommander:wealthcommander main.py /app/
COPY --chown=wealthcommander:wealthcommander core/ /app/core/
COPY --chown=wealthcommander:wealthcommander static/ /app/static/
COPY --chown=wealthcommander:wealthcommander config/ /app/config/

# Switch to non-root user
USER wealthcommander

# Health check for container monitoring
HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Expose port
EXPOSE $PORT

# Optimized startup command for NAS
CMD ["python", "-m", "uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "1", \
     "--timeout-keep-alive", "30", \
     "--log-level", "info"]