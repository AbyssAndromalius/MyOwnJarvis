#!/usr/bin/env bash
#
# init_data.sh - Initialise l'arborescence data/ nécessaire au système
#
# Crée les répertoires attendus par les sidecars si absents.
# Idempotent — peut être relancé sans risque.
#
# Arborescence créée:
#   data/
#   ├── voice/
#   │   ├── embeddings/       ← speaker embeddings (.npy) après enroll_user.py
#   │   └── access_logs/      ← logs JSONL d'identification vocale
#   ├── memory/               ← ChromaDB persistent storage (LLM sidecar)
#   └── learning/
#       ├── pending/          ← corrections en attente de validation
#       ├── approved/         ← corrections approuvées par admin
#       ├── rejected/         ← corrections rejetées
#       └── applied/          ← corrections appliquées à la mémoire
#

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data"

# Couleurs
GREEN='\033[0;32m'
NC='\033[0m'

created=0

ensure_dir() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo -e "  ${GREEN}+${NC} $dir"
        created=$((created + 1))
    fi
}

# Voice sidecar
ensure_dir "$DATA_DIR/voice/embeddings"
ensure_dir "$DATA_DIR/voice/access_logs"

# LLM sidecar — ChromaDB
ensure_dir "$DATA_DIR/memory"

# Learning sidecar
ensure_dir "$DATA_DIR/learning/pending"
ensure_dir "$DATA_DIR/learning/approved"
ensure_dir "$DATA_DIR/learning/rejected"
ensure_dir "$DATA_DIR/learning/applied"

# Logs (aussi utilisé par start_all.sh, mais autant être complet)
ensure_dir "$PROJECT_ROOT/logs"

if [ $created -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} All data directories already exist"
else
    echo -e "  ${GREEN}✓${NC} Created $created directory(ies)"
fi
