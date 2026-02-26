# Go Orchestrator - API Examples

This file contains example curl commands to test the orchestrator endpoints.

## Prerequisites

Ensure the orchestrator and all sidecars are running:
- Orchestrator: http://localhost:8080
- Voice Sidecar: http://localhost:10001
- LLM Sidecar: http://localhost:10002
- Learning Sidecar: http://localhost:10003

## Health Check

Check the health of all sidecars:

```bash
curl -X GET http://localhost:8080/health | jq
```

Expected response when all healthy:
```json
{
  "status": "ok",
  "sidecars": {
    "voice": {
      "status": "ok",
      "latency_ms": 12
    },
    "llm": {
      "status": "ok",
      "latency_ms": 8
    },
    "learning": {
      "status": "ok",
      "latency_ms": 5
    }
  }
}
```

## Text Chat

Send a text message with explicit user_id:

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "dad",
    "message": "Explain the difference between TCP and UDP",
    "conversation_history": []
  }' | jq
```

Expected response:
```json
{
  "response": "TCP (Transmission Control Protocol) is connection-oriented...",
  "model_used": "llama3.1:8b-instruct-q4_0",
  "memories_used": ["networking_preferences"],
  "user_id": "dad"
}
```

### Chat with Conversation History

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "mom",
    "message": "What about QUIC?",
    "conversation_history": [
      {
        "role": "user",
        "content": "Explain the difference between TCP and UDP"
      },
      {
        "role": "assistant",
        "content": "TCP is connection-oriented while UDP is connectionless..."
      }
    ]
  }' | jq
```

### Invalid User ID (expect 400)

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "unknown",
    "message": "Hello"
  }' | jq
```

Expected error:
```json
{
  "error": "invalid user_id",
  "detail": "user_id must be one of: dad, mom, teen, child"
}
```

## Voice Request

Send a WAV file for speaker identification and transcription:

```bash
# Assuming you have a file named audio.wav
curl -X POST http://localhost:8080/voice \
  -F "file=@audio.wav" | jq
```

Expected response (identified):
```json
{
  "status": "identified",
  "user_id": "mom",
  "confidence": 0.87,
  "transcript": "What's the weather today?",
  "response": "Today will be partly cloudy with temperatures around 22°C...",
  "model_used": "llama3.1:8b-instruct-q4_0",
  "fallback": false,
  "memories_used": ["weather_preferences"]
}
```

Expected response (fallback):
```json
{
  "status": "fallback",
  "user_id": "dad",
  "confidence": 0.0,
  "transcript": "Set timer for 5 minutes",
  "response": "I've set a timer for 5 minutes.",
  "model_used": "llama3.1:8b-instruct-q4_0",
  "fallback": true
}
```

Expected response (no_speech):
```json
{
  "status": "no_speech"
}
```

Expected response (rejected):
```json
{
  "status": "rejected",
  "confidence": 0.41
}
```

## Learning Submission

Submit a learning entry for processing:

```bash
curl -X POST http://localhost:8080/learn \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "teen",
    "content": "The math exam is on Friday at 2pm",
    "source": "user_correction"
  }' | jq
```

Expected response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing"
}
```

### Learning with Different Sources

```bash
# User correction
curl -X POST http://localhost:8080/learn \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "child",
    "content": "My birthday is June 15th",
    "source": "user_correction"
  }' | jq

# System observation
curl -X POST http://localhost:8080/learn \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "dad",
    "content": "User frequently asks about stock prices at 9am",
    "source": "system_observation"
  }' | jq
```

## Error Cases

### Method Not Allowed

```bash
curl -X GET http://localhost:8080/chat | jq
```

Expected error:
```json
{
  "error": "method not allowed",
  "detail": ""
}
```

### Missing Required Fields

```bash
# Missing message
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "dad"}' | jq

# Missing user_id
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}' | jq
```

### Sidecar Unavailable (expect 503)

If the LLM sidecar is down:

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "dad",
    "message": "Hello"
  }' | jq
```

Expected error:
```json
{
  "error": "llm sidecar unavailable",
  "detail": "failed to execute request: ..."
}
```

## Load Testing

### Simple load test with ab (ApacheBench)

```bash
# 1000 requests, 10 concurrent
ab -n 1000 -c 10 -p chat_payload.json -T application/json \
  http://localhost:8080/chat
```

Where `chat_payload.json` contains:
```json
{
  "user_id": "dad",
  "message": "test",
  "conversation_history": []
}
```

### Health check load test

```bash
ab -n 1000 -c 50 http://localhost:8080/health
```

## Monitoring

### Watch health status continuously

```bash
watch -n 1 'curl -s http://localhost:8080/health | jq'
```

### Follow logs

If running with journald:
```bash
journalctl -u assistant -f
```

Or if running in foreground, pipe to jq for pretty logs:
```bash
./build/assistant 2>&1 | jq -R 'fromjson?'
```

## Testing Degraded State

### Stop one sidecar

```bash
# Stop LLM sidecar (example)
sudo systemctl stop llm-sidecar

# Check health
curl http://localhost:8080/health | jq
```

Expected response:
```json
{
  "status": "degraded",
  "sidecars": {
    "voice": {"status": "ok", "latency_ms": 12},
    "llm": {"status": "unreachable"},
    "learning": {"status": "ok", "latency_ms": 5}
  }
}
```

## Valid User IDs

The following user IDs are valid:
- `dad`
- `mom`
- `teen`
- `child`

Any other user_id will return a 400 error.
