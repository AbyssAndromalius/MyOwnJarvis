#!/usr/bin/env bash
#
# smoke_test.sh - Tests de validation du système d'assistant personnel local
# Prérequis: le système doit être démarré avec start_all.sh
#

set -u

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE_URL="http://localhost:10080"
FIXTURES_DIR="$SCRIPT_DIR/test_fixtures"
SILENCE_WAV="$FIXTURES_DIR/silence.wav"

# Compteurs de tests
TOTAL_TESTS=8
PASSED_TESTS=0
FAILED_TESTS=0

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Vérifier la présence de jq
if ! command -v jq &> /dev/null; then
    echo -e "${RED}[error]${NC} jq is required but not installed"
    echo "Install with: sudo apt-get install jq (Debian/Ubuntu) or brew install jq (macOS)"
    exit 1
fi

# Vérifier que le système est démarré
if ! curl -sf "$BASE_URL/health" >/dev/null 2>&1; then
    echo -e "${RED}[error]${NC} Go Orchestrator is not responding on $BASE_URL"
    echo "Please start the system first with: ./scripts/start_all.sh"
    exit 1
fi

# Créer le répertoire de fixtures
mkdir -p "$FIXTURES_DIR"

# Fonction pour créer le fichier silence.wav
create_silence_wav() {
    if [ -f "$SILENCE_WAV" ]; then
        return 0
    fi
    
    # Essayer avec sox
    if command -v sox &> /dev/null; then
        sox -n -r 16000 -c 1 -b 16 "$SILENCE_WAV" trim 0.0 1.0 2>/dev/null
        return $?
    fi
    
    # Essayer avec ffmpeg
    if command -v ffmpeg &> /dev/null; then
        ffmpeg -f lavfi -i anullsrc=r=16000:cl=mono -t 1 -acodec pcm_s16le "$SILENCE_WAV" -y &>/dev/null
        return $?
    fi
    
    # Essayer de copier depuis le sidecar voice
    local voice_fixture="$PROJECT_ROOT/sidecars/voice/tests/fixtures/silence.wav"
    if [ -f "$voice_fixture" ]; then
        cp "$voice_fixture" "$SILENCE_WAV"
        return $?
    fi
    
    echo -e "${YELLOW}[warn]${NC} Could not create silence.wav (sox, ffmpeg not found, and fixture not available)"
    return 1
}

# Fonction d'affichage des résultats
print_test_header() {
    local num="$1"
    local total="$2"
    local name="$3"
    printf "[%d/%d] %-35s" "$num" "$total" "$name"
}

print_pass() {
    local detail="${1:-}"
    echo -e " ${GREEN}PASS${NC}${detail:+ ($detail)}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
}

print_fail() {
    local detail="$1"
    echo -e " ${RED}FAIL${NC} ($detail)"
    FAILED_TESTS=$((FAILED_TESTS + 1))
}

# Fonction pour afficher la réponse en cas d'échec
show_response() {
    local response="$1"
    echo -e "${YELLOW}Response:${NC}"
    echo "$response" | jq '.' 2>/dev/null || echo "$response"
    echo
}

echo
echo -e "${GREEN}[smoke]${NC} Starting smoke tests against $BASE_URL"
echo

# =============================================================================
# Test 1: Health check global
# =============================================================================
print_test_header 1 $TOTAL_TESTS "Health check global"

response=$(curl -sf "$BASE_URL/health" 2>/dev/null)
http_code=$(curl -sf -o /dev/null -w "%{http_code}" "$BASE_URL/health" 2>/dev/null)

if [ "$http_code" = "200" ]; then
    status=$(echo "$response" | jq -r '.status // empty' 2>/dev/null)
    if [ "$status" = "ok" ] || [ "$status" = "degraded" ]; then
        print_pass "status=$status"
    else
        print_fail "status=$status (expected ok or degraded)"
        show_response "$response"
    fi
else
    print_fail "HTTP $http_code (expected 200)"
    show_response "$response"
fi

# =============================================================================
# Test 2: Chat texte profil dad
# =============================================================================
print_test_header 2 $TOTAL_TESTS "Chat dad"

payload='{"user_id":"dad","message":"Dis bonjour en une phrase.","conversation_history":[]}'
response=$(curl -sf -X POST -H "Content-Type: application/json" -d "$payload" "$BASE_URL/chat" 2>/dev/null)
http_code=$(curl -sf -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$payload" "$BASE_URL/chat" 2>/dev/null)

if [ "$http_code" = "200" ]; then
    chat_response=$(echo "$response" | jq -r '.response // empty' 2>/dev/null)
    user_id=$(echo "$response" | jq -r '.user_id // empty' 2>/dev/null)
    model=$(echo "$response" | jq -r '.model_used // empty' 2>/dev/null)
    
    if [ -n "$chat_response" ] && [ "$user_id" = "dad" ]; then
        print_pass "model=$model"
    else
        print_fail "response empty or user_id mismatch"
        show_response "$response"
    fi
else
    print_fail "HTTP $http_code (expected 200)"
    show_response "$response"
fi

# =============================================================================
# Test 3: Chat texte profil child (doit router vers 3b)
# =============================================================================
print_test_header 3 $TOTAL_TESTS "Chat child"

payload='{"user_id":"child","message":"Raconte-moi une courte histoire.","conversation_history":[]}'
response=$(curl -sf -X POST -H "Content-Type: application/json" -d "$payload" "$BASE_URL/chat" 2>/dev/null)
http_code=$(curl -sf -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$payload" "$BASE_URL/chat" 2>/dev/null)

if [ "$http_code" = "200" ]; then
    model=$(echo "$response" | jq -r '.model_used // empty' 2>/dev/null)
    
    if echo "$model" | grep -q "3b"; then
        print_pass "model=$model"
    else
        print_fail "model=$model (expected 3b model)"
        show_response "$response"
    fi
else
    print_fail "HTTP $http_code (expected 200)"
    show_response "$response"
fi

# =============================================================================
# Test 4: user_id invalide
# =============================================================================
print_test_header 4 $TOTAL_TESTS "Invalid user_id"

payload='{"user_id":"unknown","message":"test","conversation_history":[]}'
http_code=$(curl -sf -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$payload" "$BASE_URL/chat" 2>/dev/null)

if [ "$http_code" = "400" ]; then
    print_pass "HTTP 400"
else
    response=$(curl -sf -X POST -H "Content-Type: application/json" -d "$payload" "$BASE_URL/chat" 2>/dev/null)
    print_fail "HTTP $http_code (expected 400)"
    show_response "$response"
fi

# =============================================================================
# Test 5: Soumission learning
# =============================================================================
print_test_header 5 $TOTAL_TESTS "Learning submit"

payload='{"user_id":"dad","content":"Le serveur de prod tourne sur Ubuntu 24.04","source":"user_correction"}'
response=$(curl -sf -X POST -H "Content-Type: application/json" -d "$payload" "$BASE_URL/learn" 2>/dev/null)
http_code=$(curl -sf -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$payload" "$BASE_URL/learn" 2>/dev/null)

learning_id=""
if [ "$http_code" = "200" ]; then
    learning_id=$(echo "$response" | jq -r '.id // empty' 2>/dev/null)
    status=$(echo "$response" | jq -r '.status // empty' 2>/dev/null)
    
    if [ -n "$learning_id" ] && [ "$status" = "processing" ]; then
        print_pass "id=$learning_id"
    else
        print_fail "missing id or status != processing"
        show_response "$response"
    fi
else
    print_fail "HTTP $http_code (expected 200)"
    show_response "$response"
fi

# =============================================================================
# Test 6: Learning status
# =============================================================================
print_test_header 6 $TOTAL_TESTS "Learning status"

if [ -n "$learning_id" ]; then
    response=$(curl -sf "http://localhost:10003/learning/status/$learning_id" 2>/dev/null)
    http_code=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:10003/learning/status/$learning_id" 2>/dev/null)
    
    if [ "$http_code" = "200" ]; then
        final_status=$(echo "$response" | jq -r '.final_status // empty' 2>/dev/null)
        
        if [ -n "$final_status" ]; then
            print_pass "status=$final_status"
        else
            print_fail "final_status not present"
            show_response "$response"
        fi
    else
        print_fail "HTTP $http_code (expected 200)"
        show_response "$response"
    fi
else
    print_fail "no learning_id from previous test"
fi

# =============================================================================
# Test 7: Voice no_speech
# =============================================================================
print_test_header 7 $TOTAL_TESTS "Voice no_speech"

# Créer le fichier silence.wav si nécessaire
if ! create_silence_wav; then
    print_fail "could not create silence.wav"
else
    response=$(curl -sf -X POST -F "file=@$SILENCE_WAV" "$BASE_URL/voice" 2>/dev/null)
    http_code=$(curl -sf -o /dev/null -w "%{http_code}" -X POST -F "file=@$SILENCE_WAV" "$BASE_URL/voice" 2>/dev/null)
    
    if [ "$http_code" = "200" ]; then
        status=$(echo "$response" | jq -r '.status // empty' 2>/dev/null)
        
        if [ "$status" = "no_speech" ]; then
            print_pass "status=no_speech"
        else
            print_fail "status=$status (expected no_speech)"
            show_response "$response"
        fi
    else
        print_fail "HTTP $http_code (expected 200)"
        show_response "$response"
    fi
fi

# =============================================================================
# Test 8: Sidecar health directs
# =============================================================================
print_test_header 8 $TOTAL_TESTS "Sidecar health directs"

voice_code=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:10001/health" 2>/dev/null)
llm_code=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:10002/health" 2>/dev/null)
learning_code=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:10003/health" 2>/dev/null)

passed=0
if [ "$voice_code" = "200" ]; then passed=$((passed + 1)); fi
if [ "$llm_code" = "200" ]; then passed=$((passed + 1)); fi
if [ "$learning_code" = "200" ]; then passed=$((passed + 1)); fi

if [ $passed -eq 3 ]; then
    print_pass "3/3"
else
    print_fail "$passed/3 (Voice:$voice_code LLM:$llm_code Learning:$learning_code)"
fi

# =============================================================================
# Résumé final
# =============================================================================
echo
if [ $PASSED_TESTS -eq $TOTAL_TESTS ]; then
    echo -e "${GREEN}[smoke]${NC} Results: ${GREEN}${PASSED_TESTS}/${TOTAL_TESTS} passed${NC}"
    echo
    exit 0
else
    echo -e "${RED}[smoke]${NC} Results: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${RED}${FAILED_TESTS} failed${NC}"
    echo
    exit 1
fi
