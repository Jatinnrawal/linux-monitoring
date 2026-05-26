#!/usr/bin/env bash
# ============================================================
#  cleanup.sh  —  Remove old reports and Docker artefacts
# ============================================================
set -euo pipefail

YELLOW='\033[1;33m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
log() { echo -e "${CYAN}[CLEAN]${NC} $*"; }
ok()  { echo -e "${GREEN}[OK]${NC}    $*"; }

REPORTS_DIR="${REPORTS_DIR:-./reports}"
KEEP_DAYS="${KEEP_DAYS:-7}"
IMAGE="devops-health-monitor"

# ── Old reports ───────────────────────────────────────────────
if [ -d "${REPORTS_DIR}" ]; then
    COUNT=$(find "${REPORTS_DIR}" -name "*.json" -mtime "+${KEEP_DAYS}" | wc -l)
    if [ "${COUNT}" -gt 0 ]; then
        log "Removing ${COUNT} report(s) older than ${KEEP_DAYS} days …"
        find "${REPORTS_DIR}" -name "*.json" -mtime "+${KEEP_DAYS}" -delete
        ok "Old reports cleaned."
    else
        log "No old reports to clean."
    fi
fi

# ── Dangling Docker images ────────────────────────────────────
if command -v docker &>/dev/null; then
    DANGLING=$(docker images -f "dangling=true" -q | wc -l)
    if [ "${DANGLING}" -gt 0 ]; then
        log "Removing ${DANGLING} dangling Docker image(s) …"
        docker image prune -f
        ok "Dangling images removed."
    fi

    # Remove old tagged versions (keep :latest)
    OLD=$(docker images "${IMAGE}" --format "{{.Tag}}" \
          | grep -v "latest" | wc -l || true)
    if [ "${OLD}" -gt 0 ]; then
        log "Removing ${OLD} old ${IMAGE} image tag(s) …"
        docker images "${IMAGE}" --format "{{.Repository}}:{{.Tag}}" \
          | grep -v "latest" | xargs -r docker rmi || true
    fi
fi

ok "Cleanup complete."
