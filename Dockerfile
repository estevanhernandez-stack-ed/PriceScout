# PriceScout Production Dockerfile
# Version: 1.0.0
# Date: November 13, 2025
# 
# Multi-stage build optimized for:
# - Playwright browser automation (Chromium)
# - Streamlit web framework
# - PostgreSQL database connectivity
# - Azure App Service deployment
#
# Build: docker build -t pricescout:latest .
# Run:   docker run -p 8000:8000 -e DATABASE_URL=... pricescout:latest

# ==============================================================================
# STAGE 1: Base Image with System Dependencies
# ==============================================================================

FROM python:3.11-slim-bookworm AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies required for Playwright and PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libwayland-client0 \
    # PostgreSQL client libraries
    libpq5 \
    # Build tools (needed for some Python packages)
    gcc \
    g++ \
    make \
    # Utilities
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ==============================================================================
# STAGE 2: Python Dependencies
# ==============================================================================

FROM base AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# Copy requirements file
COPY requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Install Playwright and download Chromium browser
RUN pip install playwright==1.55.0 && \
    playwright install chromium && \
    playwright install-deps chromium

# ==============================================================================
# STAGE 3: Final Production Image
# ==============================================================================

FROM base AS production

# Set application metadata
LABEL maintainer="626labs LLC" \
      version="1.0.0" \
      description="PriceScout - Theater Pricing Intelligence" \
      org.opencontainers.image.source="https://github.com/estevanhernandez-stack-ed/PriceScout"

# Create non-root user for security
RUN groupadd -r pricescout && \
    useradd -r -g pricescout -u 1000 -m -s /bin/bash pricescout

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy Playwright browsers from builder
COPY --from=builder /root/.cache/ms-playwright /home/pricescout/.cache/ms-playwright

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Playwright configuration
    PLAYWRIGHT_BROWSERS_PATH=/home/pricescout/.cache/ms-playwright \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    PLAYWRIGHT_HEADLESS=true \
    # Application configuration
    HOST=0.0.0.0 \
    PORT=8000 \
    DEPLOYMENT_ENV=azure \
    # Streamlit configuration
    STREAMLIT_SERVER_PORT=8000 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none

# Create application directories
RUN mkdir -p /app /app/data /app/logs /app/reports /app/debug_snapshots && \
    chown -R pricescout:pricescout /app /home/pricescout/.cache

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=pricescout:pricescout . /app/

# Create Streamlit config directory and config file
RUN mkdir -p /home/pricescout/.streamlit && \
    chown -R pricescout:pricescout /home/pricescout/.streamlit

# Create Streamlit configuration
RUN echo '[server]\n\
port = 8000\n\
address = "0.0.0.0"\n\
headless = true\n\
\n\
[browser]\n\
gatherUsageStats = false\n\
serverAddress = "0.0.0.0"\n\
serverPort = 8000\n\
\n\
[theme]\n\
primaryColor = "#FF4B4B"\n\
backgroundColor = "#0E1117"\n\
secondaryBackgroundColor = "#262730"\n\
textColor = "#FAFAFA"\n\
font = "sans serif"\n\
' > /home/pricescout/.streamlit/config.toml && \
    chown pricescout:pricescout /home/pricescout/.streamlit/config.toml

# Switch to non-root user
USER pricescout

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/_stcore/health || exit 1

# Set entrypoint and command
ENTRYPOINT ["python", "-m", "streamlit", "run"]
CMD ["app/price_scout_app.py", \
     "--server.port=8000", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]

# ==============================================================================
# BUILD METADATA
# ==============================================================================

# Build arguments for versioning
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=1.0.0

# Add labels
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.title="PriceScout" \
      org.opencontainers.image.description="Theater pricing intelligence and competitive analysis" \
      org.opencontainers.image.vendor="626labs LLC" \
      org.opencontainers.image.licenses="Proprietary"
