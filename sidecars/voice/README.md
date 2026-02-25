# Voice Sidecar

Voice processing service: VAD → Speaker Identification → Transcription

## Quick Start

```bash
./quickstart.sh  # Auto-setup
source venv/bin/activate
python scripts/enroll_user.py --user dad --samples sample1.wav sample2.wav sample3.wav
uvicorn main:app --port 10001
curl http://localhost:10001/health
```

## System Requirements

- Ubuntu Linux + NVIDIA GPU (RTX 4070 Ti Super or similar)
- Python 3.11+, CUDA compatible with PyTorch 2.1.2

## Installation

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
mkdir -p ../../data/voice/{embeddings,access_logs}
```

## Configuration (config.yaml)

```yaml
speaker_id:
  confidence_high: 0.75    # ≥ 0.75 → normal identification
  confidence_low: 0.60     # 0.60-0.74 → fallback mode, < 0.60 → rejected
  fallback_hierarchy: ["child", "teen", "mom", "dad"]  # Most → least restrictive
```

## API Endpoints

### POST /voice/process
Process audio through VAD → Speaker ID → Transcription pipeline.

**Request:** `curl -X POST http://localhost:10001/voice/process -F 'file=@audio.wav'`

**Responses:**
- **Identified (≥0.75):** `{"status":"identified", "user_id":"dad", "confidence":0.87, "transcript":"...", "fallback":false}`
- **Fallback (0.60-0.74):** `{"status":"fallback", "user_id":"child", "confidence":0.67, "transcript":"...", "fallback":true, "fallback_reason":"ambiguous_candidates: [teen, child]"}`
- **Rejected (<0.60):** `{"status":"rejected", "user_id":null, "confidence":0.41, "transcript":null}`
- **No Speech:** `{"status":"no_speech", "user_id":null, ...}`

### POST /voice/reload-embeddings
Hot-reload embeddings after enrollment: `curl -X POST http://localhost:10001/voice/reload-embeddings`

### GET /health
`curl http://localhost:10001/health`

## Enrollment

```bash
python scripts/enroll_user.py --user dad --samples audio/dad/*.wav
# Repeat for mom, teen, child
curl -X POST http://localhost:10001/voice/reload-embeddings  # Hot reload
```

## Decision Logic

| Confidence | Action | Profile Returned |
|------------|--------|------------------|
| ≥ 0.75 | Normal ID | Identified user |
| 0.60-0.74 | Fallback | Most restrictive among candidates ≥0.60 |
| < 0.60 | Reject | null (no transcription) |

**Fallback Example:** If dad=0.71, mom=0.63, others <0.60 → Returns **mom** (most restrictive among [dad, mom]), not child (child not in candidates).

**Transcription:** Happens for all confidence ≥ 0.60 (includes fallback mode).

## Testing

```bash
pytest tests/ -v  # 37 tests, no GPU required (uses mocks)
```

## Access Logging

All attempts logged to `data/voice/access_logs/access_log.jsonl`:
```json
{"timestamp":"2026-02-25T10:30:00Z", "event":"identified", "user_id":"dad", "confidence":0.82, ...}
{"timestamp":"2026-02-25T10:31:00Z", "event":"fallback", "user_id":"child", "confidence":0.67, "fallback_reason":"ambiguous_candidates: [teen, child]", ...}
```

## Files

```
voice/
├── main.py              # FastAPI app
├── pipeline.py          # Orchestrator
├── vad.py              # Silero VAD
├── speaker_id.py       # Resemblyzer + decision logic
├── transcription.py    # Faster Whisper
├── config.py           # Pydantic config loader
├── access_logger.py    # JSONL logger
├── scripts/enroll_user.py
└── tests/
    ├── test_speaker_id.py  # 22 tests
    └── test_pipeline.py    # 15 tests
```

## Performance (RTX 4070 Ti Super)

- VAD: ~50ms, Speaker ID: ~100ms, Transcription: ~200-500ms/sec
- VRAM: base ~1GB, small ~1.5GB, medium ~2.5GB

## Troubleshooting

- **Missing GPU:** Auto-fallback to CPU (slower), or set `device: "cpu"` in config.yaml
- **Missing embeddings:** Service starts with degraded status, check `/health`
- **Permission errors:** `chmod 755 ../../data/voice/access_logs`
