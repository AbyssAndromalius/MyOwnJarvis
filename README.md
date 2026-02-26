# Go Orchestrator - Personal Assistant Backend

The central orchestration component for a local personal assistant system. This Go service acts as the single entry point, routing requests to three Python FastAPI sidecars: Voice, LLM, and Learning.

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       v
┌─────────────────┐
│ Go Orchestrator │ (port 8080)
└────┬─┬─┬────────┘
     │ │ │
     v v v
  ┌──┴──┴──┴─────────────┐
  │                      │
  v                      v
┌────────┐  ┌─────┐  ┌──────────┐
│ Voice  │  │ LLM │  │ Learning │
│ :10001 │  │:10002│  │ :10003   │
└────────┘  └─────┘  └──────────┘
```

## Requirements

- Go 1.22+
- Linux (Ubuntu)
- Three FastAPI sidecars running locally:
  - Voice: http://localhost:10001
  - LLM: http://localhost:10002
  - Learning: http://localhost:10003

## Installation

```bash
# Clone the repository
cd go-orchestrator

# Download dependencies
go mod download

# Run tests
go test ./...

# Build
go build ./cmd/assistant

# Run
./assistant
```

## Configuration

Edit `config.yaml` to configure the server and sidecar endpoints:

```yaml
server:
  port: 8080
  read_timeout_seconds: 30
  write_timeout_seconds: 60

sidecars:
  voice_url: "http://localhost:10001"
  llm_url: "http://localhost:10002"
  learning_url: "http://localhost:10003"
  timeout_seconds: 30

valid_user_ids:
  - dad
  - mom
  - teen
  - child
```

## API Endpoints

### POST /chat
Text-based conversation with explicit user_id.

**Request:**
```json
{
  "user_id": "dad",
  "message": "Explain TCP vs UDP",
  "conversation_history": [
    {
      "role": "user",
      "content": "What is networking?"
    },
    {
      "role": "assistant", 
      "content": "Networking is..."
    }
  ]
}
```

**Response:**
```json
{
  "response": "...",
  "model_used": "llama3.1:8b-instruct-q4_0",
  "memories_used": ["..."],
  "user_id": "dad"
}
```

### POST /voice
Voice-based request with speaker identification.

**Request:** multipart/form-data with `file` field containing WAV audio

**Response (identified/fallback):**
```json
{
  "status": "identified",
  "user_id": "mom",
  "confidence": 0.87,
  "transcript": "...",
  "response": "...",
  "model_used": "...",
  "fallback": false
}
```

**Response (no_speech):**
```json
{
  "status": "no_speech"
}
```

**Response (rejected):**
```json
{
  "status": "rejected",
  "confidence": 0.41
}
```

### POST /learn
Submit learning content for processing.

**Request:**
```json
{
  "user_id": "mom",
  "content": "The meeting is at 9am",
  "source": "user_correction"
}
```

**Response:**
```json
{
  "id": "uuid",
  "status": "processing"
}
```

### GET /health
Aggregated health check for all sidecars.

**Response:**
```json
{
  "status": "ok",
  "sidecars": {
    "voice":    {"status": "ok", "latency_ms": 12},
    "llm":      {"status": "ok", "latency_ms": 8},
    "learning": {"status": "ok", "latency_ms": 5}
  }
}
```

**Overall status:**
- `ok` - all sidecars responding
- `degraded` - at least one sidecar unreachable
- `error` - all sidecars unreachable

## Error Handling

All errors return structured JSON:

```json
{
  "error": "error message",
  "detail": "additional details"
}
```

**HTTP Status Codes:**
- `200` - Success (including /health with degraded status)
- `400` - Bad request (invalid user_id, missing fields)
- `405` - Method not allowed
- `503` - Sidecar unavailable (except /health which always returns 200)

## Project Structure

```
.
├── cmd/
│   └── assistant/
│       └── main.go              # Entry point
├── internal/
│   ├── config/
│   │   └── config.go            # Configuration loading
│   ├── server/
│   │   └── server.go            # HTTP server setup
│   ├── handlers/
│   │   ├── chat.go              # POST /chat handler
│   │   ├── voice.go             # POST /voice handler
│   │   ├── learn.go             # POST /learn handler
│   │   └── health.go            # GET /health handler
│   └── clients/
│       ├── llm.go               # LLM sidecar client
│       ├── voice.go             # Voice sidecar client
│       └── learning.go          # Learning sidecar client
├── config.yaml                  # Configuration file
├── go.mod
└── README.md
```

## Development

### Running Tests

```bash
# Run all tests
go test ./...

# Run tests with verbose output
go test -v ./...

# Run tests with coverage
go test -cover ./...

# Run tests for specific package
go test ./internal/handlers/...
```

### Running the Server

```bash
# Run directly with go run
go run ./cmd/assistant

# Or build and run
go build -o assistant ./cmd/assistant
./assistant
```

The server will start on port 8080 (configurable in `config.yaml`).

### Graceful Shutdown

The server handles `SIGINT` and `SIGTERM` signals for graceful shutdown:

```bash
# Send interrupt signal
Ctrl+C

# Or send SIGTERM
kill -TERM <pid>
```

## Logging

The orchestrator uses structured JSON logging via `log/slog`:

```json
{
  "time": "2024-01-15T10:30:45Z",
  "level": "INFO",
  "msg": "request completed",
  "method": "POST",
  "path": "/chat",
  "status": 200,
  "duration_ms": 123,
  "remote_addr": "127.0.0.1:12345"
}
```

## Valid User IDs

The system supports four user profiles:
- `dad`
- `mom`
- `teen`
- `child`

Any request with an invalid user_id will return `400 Bad Request`.

## Dependencies

- `gopkg.in/yaml.v3` - YAML configuration parsing
- Go standard library only (net/http, log/slog, etc.)

## License

Internal project - not for public distribution.
