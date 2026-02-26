#!/usr/bin/env bash
#
# verify_fixes.sh - Vérifie que les corrections du code review sont bien appliquées
#

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "==================================================================="
echo "  Vérification des corrections M5 (Code Review)"
echo "==================================================================="
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
START_SCRIPT="$SCRIPT_DIR/start_all.sh"
STOP_SCRIPT="$SCRIPT_DIR/stop_all.sh"

# Compteurs
PASSED=0
FAILED=0

check() {
    local desc="$1"
    local file="$2"
    local pattern="$3"
    local expected="$4"
    
    printf "%-60s" "[$desc]"
    
    if [ ! -f "$file" ]; then
        echo -e " ${RED}FAIL${NC} (file not found)"
        FAILED=$((FAILED + 1))
        return 1
    fi
    
    if grep -q "$pattern" "$file"; then
        if [ "$expected" = "present" ]; then
            echo -e " ${GREEN}OK${NC}"
            PASSED=$((PASSED + 1))
            return 0
        else
            echo -e " ${RED}FAIL${NC} (should not be present)"
            FAILED=$((FAILED + 1))
            return 1
        fi
    else
        if [ "$expected" = "absent" ]; then
            echo -e " ${GREEN}OK${NC}"
            PASSED=$((PASSED + 1))
            return 0
        else
            echo -e " ${RED}FAIL${NC} (not found)"
            FAILED=$((FAILED + 1))
            return 1
        fi
    fi
}

echo "🐛 Bug 1: Commande de démarrage Python"
echo "-------------------------------------------------------------------"
check "start_all.sh utilise uvicorn" "$START_SCRIPT" "uvicorn main:app --port" "present"
check "start_all.sh N'utilise PAS python -m app.main" "$START_SCRIPT" "python -m app.main" "absent"
echo

echo "🐛 Bug 2: Harmonisation des clés PID"
echo "-------------------------------------------------------------------"
check "start_all.sh utilise LLM_PID" "$START_SCRIPT" "LLM_PID" "present"
check "start_all.sh utilise VOICE_PID" "$START_SCRIPT" "VOICE_PID" "present"
check "start_all.sh utilise LEARNING_PID" "$START_SCRIPT" "LEARNING_PID" "present"
check "start_all.sh utilise ORCHESTRATOR_PID" "$START_SCRIPT" "ORCHESTRATOR_PID" "present"
echo
check "stop_all.sh lit LLM_PID" "$STOP_SCRIPT" "LLM_PID" "present"
check "stop_all.sh lit VOICE_PID" "$STOP_SCRIPT" "VOICE_PID" "present"
check "stop_all.sh lit LEARNING_PID" "$STOP_SCRIPT" "LEARNING_PID" "present"
check "stop_all.sh lit ORCHESTRATOR_PID" "$STOP_SCRIPT" "ORCHESTRATOR_PID" "present"
echo
check "start_all.sh N'utilise PAS LLM Sidecar_PID" "$START_SCRIPT" "LLM Sidecar_PID" "absent"
check "start_all.sh N'utilise PAS Voice_Sidecar_PID" "$START_SCRIPT" "Voice_Sidecar_PID" "absent"
check "stop_all.sh N'utilise PAS Learning_Sidecar_PID" "$STOP_SCRIPT" "Learning_Sidecar_PID" "absent"
echo

echo "==================================================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ Toutes les vérifications passées${NC} ($PASSED/$((PASSED + FAILED)))"
    echo "Les corrections du code review sont bien appliquées."
else
    echo -e "${RED}❌ Échecs détectés${NC} ($FAILED/$((PASSED + FAILED)))"
    echo "Certaines corrections ne sont pas appliquées correctement."
fi
echo "==================================================================="
echo

exit $FAILED
