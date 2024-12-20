# Stage 1: Builder stage
FROM python:3.11-slim AS builder

# Set build environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies with security flags
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        gcc \
        libc6-dev \
        pkg-config \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user and group
RUN groupadd -g 10001 app && \
    useradd -u 10001 -g app -s /bin/bash -m app

# Set up build directory
WORKDIR /build

# Install Python build dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

# Stage 2: Final runtime image
FROM python:3.11-slim

# Set runtime environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    APP_ENV=production \
    GOOGLE_APPLICATION_CREDENTIALS=/app/config/service-account.json \
    DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr=4.1.* \
        ca-certificates \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user and group
RUN groupadd -g 10001 app && \
    useradd -u 10001 -g app -s /bin/bash -m app && \
    mkdir -p /app /app/config /app/data /tmp/app && \
    chown -R app:app /app /tmp/app

# Set up application directory
WORKDIR /app

# Copy built packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application code
COPY --chown=app:app . /app/

# Configure security policies
RUN chmod -R 550 /app && \
    chmod -R 770 /tmp/app && \
    chmod 660 /app/config/* || true

# Set up health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/liveness || exit 1

# Set container labels
LABEL org.opencontainers.image.source="https://github.com/org/repo" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      security.alpha.kubernetes.io/seccomp-profile="runtime/default" \
      security.alpha.kubernetes.io/unsafe-sysctls="none"

# Drop all capabilities and run as non-root
USER app:app

# Expose API port
EXPOSE 8000/tcp

# Set up volume mounts
VOLUME ["/app/data", "/tmp/app"]

# Define entry points
ENTRYPOINT ["python", "-m"]
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--limit-concurrency", "1000"]