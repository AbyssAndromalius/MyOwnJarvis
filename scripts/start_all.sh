#!/usr/bin/env bash
#
# start_all.sh - Démarre tous les composants du système d'assistant personnel local
# Ordre: init_data → LLM Sidecar → Voice Sidecar → Learning Sidecar → Go Orchestrator
#

set -u

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
PID_FILE="$LOG_DIR/pids.env"
MAX_WAIT=30
RETRY_INTERVAL=2

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Créer le répertoire de logs si nécessaire
mkdir -p "$LOG_DIR"

# Fonction d'affichage
log() {
    echo -e "${GREEN}[start]${NC} $*"
}

error() {
    echo -e "${RED}[error]${NC} $*" >&2
}

warn() {
    echo -e "${YELLOW}[warn]${NC} $*"
}

# Vérifier qu'aucune instance n'est déjà en cours
if [ -f "$PID_FILE" ]; then
    running=0
    while IFS='=' read -r var_name pid; do
        if ps -p "$pid" > /dev/null 2>&1; then
            running=$((running + 1))
        fi
    done < "$PID_FILE"

    if [ $running -gt 0 ]; then
        error "System appears to be already running ($running process(es) active)"
        error "Run ./scripts/stop_all.sh first, or delete $PID_FILE if stale"
        exit 1
    fi
    # Stale PID file — clean it up
    rm -f "$PID_FILE"
fi

# Fonction pour attendre qu'un service réponde sur son endpoint /health
wait_for_health() {
    local name="$1"
    local port="$2"
    local url="http://localhost:$port/health"
    local elapsed=0
    local start_time=$(date +%s)
    
    while [ $elapsed -lt $MAX_WAIT ]; do
        if curl -sf "$url" >/dev/null 2>&1; then
            local end_time=$(date +%s)
            local duration=$((end_time - start_time))
            log "$name ready (${duration}s)"
            return 0
        fi
        sleep $RETRY_INTERVAL
        elapsed=$((elapsed + RETRY_INTERVAL))
    done
    
    error "$name did not respond within ${MAX_WAIT}s"
    error "Check logs: $LOG_DIR/"
    return 1
}

# Fonction pour démarrer un sidecar Python
start_python_sidecar() {
    local name="$1"
    local dir="$2"
    local port="$3"
    local log_file="$LOG_DIR/${name// /_}.log"
    
    log "Starting $name on :$port..."
    
    local sidecar_dir="$PROJECT_ROOT/sidecars/$dir"
    if [ ! -d "$sidecar_dir" ]; then
        error "Directory sidecars/$dir not found"
        return 1
    fi
    
    # Activer le venv si présent
    if [ -d "$sidecar_dir/venv" ]; then
        source "$sidecar_dir/venv/bin/activate"
    fi
    
    # Démarrer le sidecar en arrière-plan (depuis son propre répertoire pour les configs relatifs)
    (cd "$sidecar_dir" && uvicorn main:app --host 127.0.0.1 --port "$port" >> "$log_file" 2>&1) &
    local pid=$!
    
    # Sauvegarder le PID
    local pid_key
    case "$name" in
        "LLM Sidecar")      pid_key="LLM_PID" ;;
        "Voice Sidecar")     pid_key="VOICE_PID" ;;
        "Learning Sidecar")  pid_key="LEARNING_PID" ;;
        *) pid_key="${name}_PID" ;;
    esac
    echo "${pid_key}=$pid" >> "$PID_FILE.tmp"
    
    # Attendre que le service soit prêt
    if ! wait_for_health "$name" "$port"; then
        error "Failed to start $name — killing PID $pid"
        kill $pid 2>/dev/null || true
        return 1
    fi
    
    return 0
}

# Fonction pour démarrer le Go Orchestrator
start_go_orchestrator() {
    local name="Go Orchestrator"
    local port="10080"
    local log_file="$LOG_DIR/orchestrator.log"
    
    log "Starting $name on :$port..."
    
    # ──────────────────────────────────────────────────────────────
    # FIX: Lancer go run depuis la racine du projet pour que
    # config.Load("config.yaml") trouve le fichier correctement.
    # L'ancien code faisait cd cmd/assistant && go run . ce qui
    # cassait la résolution du chemin relatif vers config.yaml.
    # ──────────────────────────────────────────────────────────────
    (cd "$PROJECT_ROOT" && go run ./cmd/assistant >> "$log_file" 2>&1) &
    local pid=$!
    
    # Sauvegarder le PID
    echo "ORCHESTRATOR_PID=$pid" >> "$PID_FILE.tmp"
    
    # Attendre que le service soit prêt
    if ! wait_for_health "$name" "$port"; then
        error "Failed to start $name — killing PID $pid"
        kill $pid 2>/dev/null || true
        return 1
    fi
    
    return 0
}

# ═══════════════════════════════════════════════════════════════════
# DÉMARRAGE
# ═══════════════════════════════════════════════════════════════════

echo
log "Starting local LLM assistant system..."
echo

# 0. Initialiser les répertoires data si nécessaire
if [ -x "$SCRIPT_DIR/init_data.sh" ]; then
    log "Initializing data directories..."
    "$SCRIPT_DIR/init_data.sh"
    echo
fi

# Nettoyer les anciens PIDs
rm -f "$PID_FILE" "$PID_FILE.tmp"

# 1. LLM Sidecar (port 10002) — doit démarrer en premier (utilisé par les autres)
if ! start_python_sidecar "LLM Sidecar" "llm" "10002"; then
    error "System startup failed at LLM Sidecar"
    exit 1
fi

# 2. Voice Sidecar (port 10001)
if ! start_python_sidecar "Voice Sidecar" "voice" "10001"; then
    warn "Voice Sidecar failed — continuing without voice support"
    # Ne pas bloquer le démarrage pour le voice (GPU pas toujours dispo)
fi

# 3. Learning Sidecar (port 10003)
if ! start_python_sidecar "Learning Sidecar" "learning" "10003"; then
    error "System startup failed at Learning Sidecar"
    exit 1
fi

# 4. Go Orchestrator (port 8080)
if ! start_go_orchestrator; then
    error "System startup failed at Go Orchestrator"
    exit 1
fi

# Finaliser le fichier de PIDs
mv "$PID_FILE.tmp" "$PID_FILE"

# ═══════════════════════════════════════════════════════════════════
# RÉSUMÉ
# ═══════════════════════════════════════════════════════════════════

echo
echo -e "${GREEN}[ok]${NC} System started"
while IFS='=' read -r name pid; do
    case "$name" in
        LLM_PID)
            echo "  LLM Sidecar       PID=$pid  :10002"
            ;;
        VOICE_PID)
            echo "  Voice Sidecar     PID=$pid  :10001"
            ;;
        LEARNING_PID)
            echo "  Learning Sidecar  PID=$pid  :10003"
            ;;
        ORCHESTRATOR_PID)
            echo "  Go Orchestrator   PID=$pid  :8080"
            ;;
    esac
done < "$PID_FILE"
echo

log "All services are running. Logs available in $LOG_DIR/"
log "To stop:       ./scripts/stop_all.sh"
log "To smoke test: ./scripts/smoke_test.sh"
echo
