# Multi-Agent Dashboard - Production Dockerfile
FROM python:3.11-slim

# Security: Run as non-root user
RUN groupadd -r agents && useradd -r -g agents agent

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CHROMIUM_PATH=/usr/bin/chromium
ENV PLAYWRIGHT_BROWSERS_PATH=/usr/bin

# Security: Limit capabilities
ENV SANDBOX_ENABLED=true
ENV NO_PROXY_SERVER=true

# Create state directory
RUN mkdir -p /app/state /app/logs /app/audit && \
    chown -R agent:agents /app

# Switch to non-root user
USER agent

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; from core.orchestrator import Orchestrator; print('healthy')" || exit 1

# Default command
CMD ["python", "-m", "dashboard.server"]
