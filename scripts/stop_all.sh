#!/usr/bin/env bash
#
# stop_all.sh - Arrête proprement tous les composants du système d'assistant personnel local
#

set -u

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
PID_FILE="$LOG_DIR/pids.env"
GRACE_PERIOD=5

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[stop]${NC} $*"
}

error() {
    echo -e "${RED}[error]${NC} $*" >&2
}

warn() {
    echo -e "${YELLOW}[warn]${NC} $*"
}

# Vérifier que le fichier de PIDs existe
if [ ! -f "$PID_FILE" ]; then
    error "PID file not found: $PID_FILE"
    error "System may not be running or was not started with start_all.sh"
    exit 1
fi

echo
log "Stopping local LLM assistant system..."
echo

# Fonction pour arrêter un processus
stop_process() {
    local name="$1"
    local pid="$2"
    
    # Vérifier que le processus existe
    if ! ps -p "$pid" > /dev/null 2>&1; then
        warn "$name (PID=$pid) is not running"
        return 0
    fi
    
    log "Stopping $name (PID=$pid)..."
    
    # Envoyer SIGTERM
    kill -TERM "$pid" 2>/dev/null
    
    # Attendre le grace period
    local waited=0
    while [ $waited -lt $GRACE_PERIOD ]; do
        if ! ps -p "$pid" > /dev/null 2>&1; then
            log "$name stopped gracefully"
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    
    # Si toujours actif après le grace period, envoyer SIGKILL
    if ps -p "$pid" > /dev/null 2>&1; then
        warn "$name did not stop gracefully, sending SIGKILL"
        kill -KILL "$pid" 2>/dev/null
        sleep 1
        
        if ps -p "$pid" > /dev/null 2>&1; then
            error "Failed to stop $name (PID=$pid)"
            return 1
        else
            log "$name killed"
            return 0
        fi
    fi
    
    return 0
}

# Lire les PIDs et arrêter les processus
# Ordre inverse du démarrage: Orchestrator → Learning → Voice → LLM
declare -A pids
declare -A names

while IFS='=' read -r var_name pid; do
    case "$var_name" in
        ORCHESTRATOR_PID)
            pids[orchestrator]=$pid
            names[orchestrator]="Go Orchestrator"
            ;;
        LEARNING_PID)
            pids[learning]=$pid
            names[learning]="Learning Sidecar"
            ;;
        VOICE_PID)
            pids[voice]=$pid
            names[voice]="Voice Sidecar"
            ;;
        LLM_PID)
            pids[llm]=$pid
            names[llm]="LLM Sidecar"
            ;;
    esac
done < "$PID_FILE"

# Arrêter dans l'ordre inverse
all_stopped=true

if [ -n "${pids[orchestrator]:-}" ]; then
    stop_process "${names[orchestrator]}" "${pids[orchestrator]}" || all_stopped=false
fi

if [ -n "${pids[learning]:-}" ]; then
    stop_process "${names[learning]}" "${pids[learning]}" || all_stopped=false
fi

if [ -n "${pids[voice]:-}" ]; then
    stop_process "${names[voice]}" "${pids[voice]}" || all_stopped=false
fi

if [ -n "${pids[llm]:-}" ]; then
    stop_process "${names[llm]}" "${pids[llm]}" || all_stopped=false
fi

# Nettoyer le fichier de PIDs
rm -f "$PID_FILE"

echo
if [ "$all_stopped" = true ]; then
    echo -e "${GREEN}[ok]${NC} All services stopped successfully"
else
    error "Some services failed to stop properly"
    exit 1
fi
echo
