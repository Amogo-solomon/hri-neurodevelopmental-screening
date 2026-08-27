#!/usr/bin/env bash
###############################################################################
# setup-local.sh — One-command local development environment setup
# Starts Docker Compose stack and pulls Ollama VLM model
###############################################################################

set -euo pipefail

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

info "Starting HRI Platform local stack..."

# Prerequisites
for cmd in docker docker-compose; do
  command -v "$cmd" &>/dev/null || { warn "$cmd not found"; exit 1; }
done

cd "$ROOT_DIR"

# Start services
docker-compose up -d --build

info "Waiting for services to start..."
sleep 15

# Pull VLM model
info "Pulling LLaVA 13B model (this may take 5–10 min on first run)..."
docker-compose exec -T ollama ollama pull llava:13b || \
  warn "Could not pull model automatically. Run: docker exec hri_ollama ollama pull llava:13b"

success "Platform running!"
echo ""
echo -e "  Frontend  : ${CYAN}http://localhost:3000${NC}"
echo -e "  Backend   : ${CYAN}http://localhost:8000${NC}"
echo -e "  API docs  : ${CYAN}http://localhost:8000/api/docs${NC}"
echo -e "  Ollama    : ${CYAN}http://localhost:11434${NC}"
echo ""
echo -e "  Logs      : docker-compose logs -f"
echo -e "  Stop      : docker-compose down"
echo ""
