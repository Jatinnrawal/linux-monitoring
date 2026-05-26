# ─────────────────────────────────────────────
#  DevOps Health Monitor — Docker Image
#  Base: slim Python on Debian (no extras needed)
# ─────────────────────────────────────────────

FROM python:3.11-slim

LABEL maintainer="devops-team"
LABEL description="System Health Monitor — CPU, Memory, Disk, Services"
LABEL version="1.0"

# ---------- system packages ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        procps \
    && rm -rf /var/lib/apt/lists/*

# ---------- working directory ----------
WORKDIR /app

# ---------- copy source ----------
COPY app/       ./app/
COPY tests/     ./tests/
COPY scripts/   ./scripts/

# ---------- permissions ----------
RUN chmod +x scripts/*.sh

# ---------- reports output volume ----------
RUN mkdir -p /app/reports
VOLUME ["/app/reports"]

# ---------- environment ----------
ENV PYTHONUNBUFFERED=1 \
    THRESHOLD_CPU=80   \
    THRESHOLD_MEM=85   \
    THRESHOLD_DISK=90  \
    REPORTS_DIR=/app/reports

# ---------- default command ----------
CMD ["python3", "app/monitor.py", "--output-dir", "/app/reports"]
