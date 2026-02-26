#!/bin/bash

# Go Orchestrator - Project Validation Script
# This script validates the project structure and files

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "Go Orchestrator - Validation Report"
echo "======================================"
echo ""

# Check required files
echo "Checking required files..."

required_files=(
    "go.mod"
    "config.yaml"
    "README.md"
    "Makefile"
    "cmd/assistant/main.go"
    "internal/config/config.go"
    "internal/server/server.go"
    "internal/clients/llm.go"
    "internal/clients/voice.go"
    "internal/clients/learning.go"
    "internal/handlers/chat.go"
    "internal/handlers/voice.go"
    "internal/handlers/learn.go"
    "internal/handlers/health.go"
    "internal/clients/llm_test.go"
    "internal/clients/voice_test.go"
    "internal/clients/learning_test.go"
    "internal/handlers/chat_test.go"
    "internal/handlers/voice_test.go"
    "internal/handlers/learn_test.go"
    "internal/handlers/health_test.go"
)

missing=0
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${RED}✗${NC} $file (MISSING)"
        missing=$((missing + 1))
    fi
done

echo ""
if [ $missing -eq 0 ]; then
    echo -e "${GREEN}All required files present!${NC}"
else
    echo -e "${RED}$missing file(s) missing!${NC}"
    exit 1
fi

echo ""
echo "======================================"
echo "Project Statistics"
echo "======================================"

# Count lines of code
total_lines=0
go_files=0

for file in $(find . -name "*.go"); do
    lines=$(wc -l < "$file")
    total_lines=$((total_lines + lines))
    go_files=$((go_files + 1))
done

echo "Go files: $go_files"
echo "Total lines of Go code: $total_lines"

test_files=$(find . -name "*_test.go" | wc -l)
impl_files=$(find . -name "*.go" ! -name "*_test.go" | wc -l)

echo "Implementation files: $impl_files"
echo "Test files: $test_files"

# Calculate test coverage ratio
if [ $impl_files -gt 0 ]; then
    coverage_ratio=$(awk "BEGIN {printf \"%.1f\", ($test_files / $impl_files) * 100}")
    echo "Test file coverage: ${coverage_ratio}%"
fi

echo ""
echo "======================================"
echo "Project Structure"
echo "======================================"

tree -L 3 -I 'build|.git' . 2>/dev/null || find . -type d -maxdepth 3 | grep -v ".git" | sort

echo ""
echo "======================================"
echo "Configuration"
echo "======================================"

if [ -f "config.yaml" ]; then
    echo "config.yaml contents:"
    cat config.yaml | head -20
fi

echo ""
echo "======================================"
echo "Validation Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Install Go 1.22+ if not already installed"
echo "  2. Run 'make install' to download dependencies"
echo "  3. Run 'make test' to run all tests"
echo "  4. Run 'make build' to build the application"
echo "  5. Run './build/assistant' to start the server"
echo ""
