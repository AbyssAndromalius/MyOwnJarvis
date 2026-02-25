#!/bin/bash
set -e
echo "=== Voice Sidecar Quick Start ==="
[ ! -f "main.py" ] && echo "Error: Run from sidecars/voice/" && exit 1
command -v python3 >/dev/null 2>&1 || { echo "Python 3 required"; exit 1; }
[ ! -d "venv" ] && python3 -m venv venv && echo "✓ venv created"
source venv/bin/activate
pip install -q --upgrade pip && pip install -q -r requirements.txt
mkdir -p ../../data/voice/{embeddings,access_logs}
echo "✓ Setup complete!"
echo "Next: 1) python scripts/enroll_user.py --user dad --samples *.wav"
echo "      2) uvicorn main:app --port 10001"
echo "      3) pytest tests/ -v"
