#!/bin/bash
# Run all tests for Learning Sidecar

echo "Running Learning Sidecar tests..."
echo ""

pytest tests/ -v --tb=short

echo ""
echo "Tests completed!"
