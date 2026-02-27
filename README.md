# 🎙️ MyOwnJarvis

> A local, offline-first personal assistant with speaker identification — built for a family.

---

## Overview

MyOwnJarvis runs entirely on your machine. No cloud, no subscription, no biometric data sent anywhere. It recognizes who is speaking, adapts its responses to each family member's profile, and learns from your corrections only after your explicit approval.

```
You speak → your voice is identified → response is tailored to your profile → TTS playback
```

---

## Features

- **Speaker identification** — Recognizes dad, mom, teen (15), and child (8) by voice embedding
- **Per-profile responses** — Different tone, vocabulary, and allowed topics per speaker
- **Push-to-talk** — Button or F12 key from Edge, ESP32-compatible (future)
- **Supervised learning** — Submit a correction, it goes through 3 validation gates before being applied
- **100% local** — Ollama for LLMs, Whisper for transcription, ChromaDB for memory
- **Personal data protection** — Automatic detection, never sent to the cloud

---

## Architecture

```
Windows 11
│
└── Edge :10090  ←→  Go Client :10090
                          │
                    ┌─────┴──────┐
                    ↓            ↓
                 /voice        /chat
                    │
         ─ ─ ─ ─ WSL2 ─ ─ ─ ─ ─
                    │
          Go Orchestrator :10080
                    │
       ┌────────────┼────────────┐
       ↓            ↓            ↓
Voice :10001    LLM :10002   Learning :10003
Silero VAD      Ollama         Gate 1: LLM sanity
Resemblyzer     ChromaDB       Gate 2: fact-check
Whisper         Classifier     Gate 3: admin approval
```

### Components

| Component | Technology | Port |
|-----------|------------|------|
| Go Orchestrator | Go 1.22 | 10080 |
| Voice Sidecar | Python / FastAPI | 10001 |
| LLM Sidecar | Python / FastAPI / Ollama | 10002 |
| Learning Sidecar | Python / FastAPI | 10003 |
| Windows Client | Go 1.22 / Edge | 10090 |

---

## Family Profiles

| Profile | Role | LLM Model | Access |
|---------|------|-----------|--------|
| `dad` | admin | Llama 3.1 8B | Full |
| `mom` | admin | Llama 3.1 8B | Full |
| `teen` | user | Llama 3.2 3B | Blocked: adult content, financial advice |
| `child` | user | Llama 3.2 3B | Restricted: homework, stories, games, kid science |

Model selection is automatic. Complex or admin queries use the 8B model. Child profiles and simple exchanges use the 3B.

---

## Voice Security

```
Confidence ≥ 0.75  →  Identified  →  Exact profile
0.60 – 0.74        →  Fallback    →  Most restrictive profile among candidates
< 0.60             →  Rejected    →  Silence + log only
```

Unknown speakers never receive a response. Enrollment is CLI-only, admin-restricted.

---

## Learning Pipeline

When you submit a correction (`POST /learn`), it passes through 4 gates before being applied to memory:

```
Submission
    │
    ▼
Gate 1 — LLM sanity check (coherence + safety)
    │
    ▼
Gate 2a — Local LLM fact-check (confidence score)
    │
    ├── confidence ≥ 0.80  →  auto-approved
    └── confidence < 0.80  →  Gate 2b
                                  │
                             Claude API (optional fallback)
                                  │
                                  ▼
Gate 3 — Admin approval (desktop notification)
    │
    ▼
Applied to ChromaDB memory
```

Personal data (names, addresses, routines) is detected automatically and never routed through the cloud.

---

## Hardware Requirements

- **GPU**: NVIDIA RTX with 8 GB VRAM minimum (tested on RTX 4070 Ti Super 16 GB)
- **RAM**: 16 GB recommended
- **OS**: Windows 11 + WSL2 Ubuntu 24.04
- **Disk**: 50 GB free (LLM models included)

### VRAM Budget

| Component | VRAM |
|-----------|------|
| Llama 3.1 8B Q4 | ~8 GB |
| Llama 3.2 3B Q4 | ~2 GB |
| Whisper base | ~1 GB |
| Resemblyzer + Silero VAD | ~0.3 GB |
| **Total (8B active)** | **~9.3 GB** |

---

## Installation

See **[INSTALL_WSL2.md](./INSTALL_WSL2.md)** for the full setup guide from a fresh Windows 11 machine.

### Quick Start

```bash
# WSL — init
./scripts/init_data.sh
./scripts/start_all.sh

# WSL — validate
./scripts/smoke_test.sh

# Windows — client
cd clients/windows
go build -o assistant-client.exe
./assistant-client.exe
# Open Edge → http://localhost:10090
```

---

## Voice Enrollment

```bash
cd sidecars/voice
source venv/bin/activate

# Record WAV samples on Windows, copy them into WSL
python scripts/enroll_user.py \
    --user dad \
    --samples /mnt/c/Users/<you>/samples/dad/*.wav
```

5 samples of 5–10 seconds per person is sufficient.

---

## Reviewing Pending Corrections (Gate 3)

```bash
cd sidecars/learning
source venv/bin/activate

python scripts/review_learning.py list
python scripts/review_learning.py approve <id>
python scripts/review_learning.py reject <id>
```

---

## Project Structure

```
MyOwnJarvis/
├── cmd/assistant/          # Go Orchestrator
├── internal/               # Clients, handlers, config
├── clients/windows/        # Windows Go client + Edge interface
├── sidecars/
│   ├── llm/                # LLM Sidecar (Ollama + ChromaDB)
│   ├── voice/              # Voice Sidecar (VAD + Speaker ID + Whisper)
│   └── learning/           # Learning Sidecar (4 gates)
├── scripts/                # start / stop / smoke / init
├── configs/                # Profiles and global config
└── data/                   # Runtime data (gitignored)
```

---

## Roadmap

- [x] Go Orchestrator
- [x] Voice Sidecar (identification + transcription)
- [x] LLM Sidecar (memory + model routing)
- [x] Learning Sidecar (supervised learning)
- [x] Integration scripts
- [x] Windows Go Client (Edge + push-to-talk + TTS)
- [ ] TTS Sidecar (Piper — local voice synthesis)
- [ ] ESP32 Client (hardware push-to-talk button)
- [ ] Model upgrade to Qwen3.5-35B-A3B

---

## License

MIT
