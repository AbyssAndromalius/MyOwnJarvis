#!/bin/bash
# Start Learning Sidecar

echo "Starting Learning Sidecar on port 10003..."
uvicorn main:app --host 0.0.0.0 --port 10003 --reload
