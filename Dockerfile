# ============================================================================
# NYC Crime Pipeline — Multi-stage Docker build
#
# Stage 1 (builder): installs dependencies into a virtual env
# Stage 2 (runtime): copies only the venv + source code → minimal image
#
# Result: ~350 MB image instead of ~1.2 GB with a naive approach.
# ============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# System deps needed to compile native wheels (polars, pyarrow)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Create a virtual env inside the build stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies first (layer cache: only re-runs if deps change)
COPY pyproject.toml .
RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir pytest

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL maintainer="NYC Crime Pipeline — Tesis Ingeniería en Sistemas"

# curl for healthcheck, nothing else
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy the pre-built virtual env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy source code
COPY config/ config/
COPY src/ src/
COPY app/ app/
COPY tests/ tests/
COPY pyproject.toml .

# Data directory — will be mounted as a volume
RUN mkdir -p data/raw data/processed data/reference

# Streamlit config: disable telemetry, set server defaults
RUN mkdir -p /root/.streamlit && \
    printf '[general]\nemail = ""\n\n[server]\nheadless = true\naddress = "0.0.0.0"\nport = 8501\nenableCORS = false\nenableXsrfProtection = false\n\n[browser]\ngatherUsageStats = false\n' \
    > /root/.streamlit/config.toml

# Default command: run the dashboard
CMD ["streamlit", "run", "app/main.py"]
