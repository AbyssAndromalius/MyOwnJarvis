# Installation Guide — MyOwnJarvis
### Windows 11 + WSL2 Ubuntu 24.04 — From Scratch

---

## Prerequisites

- Windows 11 up to date (22H2 minimum)
- WSL2 with Ubuntu 24.04 installed
- NVIDIA RTX 4070 Ti Super — Windows drivers up to date (Game Ready or Studio)
- 50 GB free disk space for WSL

> **Important**: NVIDIA drivers are installed **on the Windows side only**.
> Never install NVIDIA drivers inside WSL — it will break GPU integration.

---

## Steps Overview

1. Verify and configure WSL2
2. Enable systemd in WSL2
3. WSL CUDA Toolkit (not the drivers)
4. System dependencies
5. Python 3.11
6. Go 1.22
7. Ollama
8. Clone the repo
9. Install Python sidecars
10. Build the Go Orchestrator
11. Initialize data directories
12. Voice enrollment
13. First launch + smoke tests

---

## Step 1 — Verify WSL2

From PowerShell (Windows):

```powershell
wsl --version
# Should display WSL version 2.x.x

wsl --status
# Default Version: 2
```

If Ubuntu 24.04 is not installed:

```powershell
wsl --install -d Ubuntu-24.04
```

Confirm Ubuntu is running on WSL2 (not WSL1):

```powershell
wsl --list --verbose
# Ubuntu-24.04   Running   2   ← 2 confirms WSL2
```

---

## Step 2 — Enable systemd in WSL2

systemd is required for Ollama. From the Ubuntu WSL terminal:

```bash
# Check if systemd is already active
systemctl --version 2>/dev/null && echo "systemd OK" || echo "systemd missing"
```

If missing:

```bash
sudo tee /etc/wsl.conf > /dev/null <<EOF
[boot]
systemd=true
EOF
```

Then from Windows PowerShell, restart WSL:

```powershell
wsl --shutdown
# Wait 8 seconds
wsl -d Ubuntu-24.04
```

Verify after restart:

```bash
systemctl --version   # should display systemd 255 or similar
```

---

## Step 3 — CUDA Toolkit for WSL2

> **Do not install NVIDIA drivers inside WSL.** Only install the toolkit.

First, verify the GPU is visible from WSL:

```bash
nvidia-smi
# Should display the GPU and the Windows driver version
# e.g.: NVIDIA GeForce RTX 4070 Ti Super | 16376MiB
```

If `nvidia-smi` fails, update NVIDIA drivers on the Windows side then run `wsl --shutdown` from PowerShell.

Install the WSL CUDA Toolkit:

```bash
wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
rm cuda-keyring_1.1-1_all.deb

sudo apt update
sudo apt install -y cuda-toolkit-12-3

echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc

nvcc --version   # CUDA compilation tools, release 12.3
```

---

## Step 4 — System Dependencies

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y \
    build-essential \
    curl \
    wget \
    git \
    jq \
    sox \
    ffmpeg \
    libsndfile1 \
    portaudio19-dev \
    libnotify-bin \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    pkg-config

# Verify critical tools
jq --version
sox --version
notify-send --version   # requires WSLg (included in Windows 11)
```

> **Note**: `notify-send` works via WSLg included in Windows 11.
> Gate 3 admin approval notifications will appear as regular Windows notifications.

---

## Step 5 — Python 3.11

```bash
python3.11 --version   # Python 3.11.x

sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --set python3 /usr/bin/python3.11

python3 --version   # Python 3.11.x
```

---

## Step 6 — Go 1.22

```bash
wget https://go.dev/dl/go1.22.0.linux-amd64.tar.gz
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go1.22.0.linux-amd64.tar.gz
rm go1.22.0.linux-amd64.tar.gz

echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
echo 'export GOPATH=$HOME/go' >> ~/.bashrc
source ~/.bashrc

go version   # go version go1.22.0 linux/amd64
```

---

## Step 7 — Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh

sudo systemctl enable --now ollama
systemctl status ollama   # should display active (running)

ollama --version
```

Pull the two models used by the project:

```bash
# Fast model — child/teen/small talk (~2 GB)
ollama pull llama3.2:3b-instruct-q4_0

# Full model — admin/complex queries (~5 GB)
ollama pull llama3.1:8b-instruct-q4_0

# Verify
ollama list
```

> **Note**: Download may take 10–30 minutes.
> Ollama automatically uses the GPU via CUDA for WSL2.

Test Ollama:

```bash
ollama run llama3.2:3b-instruct-q4_0 "Say hello in one sentence."
# Ctrl+D to exit
```

---

## Step 8 — Clone the Repo

```bash
# Clone into the WSL home directory — NOT into /mnt/c/ (slow I/O)
cd ~
git clone https://github.com/AbyssAndromalius/MyOwnJarvis.git
cd MyOwnJarvis
```

> **Important**: Always work inside the WSL filesystem (`~/...`),
> not in `/mnt/c/Users/...`. Windows I/O is 10x slower and may
> cause sidecar startup timeouts.

---

## Step 9 — Initialize Data Directories

```bash
cd ~/MyOwnJarvis
chmod +x scripts/*.sh
./scripts/init_data.sh
```

Expected output:

```
  + data/voice/embeddings
  + data/voice/access_logs
  + data/memory
  + data/learning/pending
  + data/learning/approved
  + data/learning/rejected
  + data/learning/applied
  + logs
  ✓ Created 8 directory(ies)
```

---

## Step 10 — Install Python Sidecars

Each sidecar has its own isolated virtualenv.

### LLM Sidecar

```bash
cd ~/MyOwnJarvis/sidecars/llm
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
cd ~/MyOwnJarvis
```

### Voice Sidecar

```bash
cd ~/MyOwnJarvis/sidecars/voice
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
cd ~/MyOwnJarvis
```

> **Note**: Resemblyzer and Faster-Whisper are installed here.
> The Whisper model (`base`, ~150 MB) is downloaded on first startup.

### Learning Sidecar

```bash
cd ~/MyOwnJarvis/sidecars/learning
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
cd ~/MyOwnJarvis
```

---

## Step 11 — Build the Go Orchestrator

```bash
cd ~/MyOwnJarvis
go mod tidy
go build ./cmd/assistant
echo "Build: $?"   # 0 = success
```

---

## Step 12 — Environment Variables (optional)

Gate 2b (Claude fact-check) is optional. Without this variable, the system
runs entirely locally and Gate 2b auto-passes.

```bash
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.bashrc
source ~/.bashrc
```

---

## Step 13 — Voice Enrollment

> WSL does not have direct microphone access — record samples on Windows first.

### Record samples on Windows

Use Windows Voice Recorder, Audacity, or any app that saves `.wav` files.
Record 5–10 clips of 5–10 seconds each, speaking naturally.
Save them to `C:\Users\<you>\samples\dad\`.

### Copy samples into WSL

```bash
mkdir -p ~/samples_dad
cp /mnt/c/Users/<your_user>/samples/dad/*.wav ~/samples_dad/
```

### Create the voice embedding

```bash
cd ~/MyOwnJarvis/sidecars/voice
source venv/bin/activate

python scripts/enroll_user.py \
    --user dad \
    --samples ~/samples_dad/sample1.wav \
               ~/samples_dad/sample2.wav \
               ~/samples_dad/sample3.wav \
               ~/samples_dad/sample4.wav \
               ~/samples_dad/sample5.wav

deactivate
```

Expected output:

```
Processed 5 samples
Saved embedding: ../../data/voice/embeddings/dad.npy
Embedding norm: 0.9998
```

Repeat for each family member:

```bash
python scripts/enroll_user.py --user mom --samples ~/samples_mom/*.wav
python scripts/enroll_user.py --user teen --samples ~/samples_teen/*.wav
python scripts/enroll_user.py --user child --samples ~/samples_child/*.wav
```

> At minimum, enroll `dad` before running smoke tests.

---

## Step 14 — Unit Tests (recommended)

```bash
# LLM Sidecar
cd ~/MyOwnJarvis/sidecars/llm
source venv/bin/activate
LLM_SIDECAR_MOCK_EMBEDDINGS=1 pytest test_classifier.py test_memory.py -v
deactivate

# Voice Sidecar
cd ~/MyOwnJarvis/sidecars/voice
source venv/bin/activate
pytest tests/ -v
deactivate

# Learning Sidecar
cd ~/MyOwnJarvis/sidecars/learning
source venv/bin/activate
pytest tests/ -v
deactivate

# Go Orchestrator
cd ~/MyOwnJarvis
go test ./... -v
```

---

## Step 15 — First Launch

```bash
cd ~/MyOwnJarvis

# Verify Ollama is running
systemctl status ollama

# Start all components
./scripts/start_all.sh
```

Expected output:

```
[start] Starting LLM Sidecar on :10002...
[start] LLM Sidecar ready (8s)
[start] Starting Voice Sidecar on :10001...
[start] Voice Sidecar ready (15s)
[start] Starting Learning Sidecar on :10003...
[start] Learning Sidecar ready (4s)
[start] Starting Go Orchestrator on :10080...
[start] Go Orchestrator ready (2s)

[ok] System started
  LLM Sidecar       PID=XXXXX  :10002
  Voice Sidecar     PID=XXXXX  :10001
  Learning Sidecar  PID=XXXXX  :10003
  Go Orchestrator   PID=XXXXX  :10080
```

Services are also accessible from Windows:

```
http://localhost:10080/health
```

---

## Step 16 — Smoke Tests

```bash
cd ~/MyOwnJarvis
./scripts/smoke_test.sh
```

Expected output:

```
[smoke] Starting smoke tests against http://localhost:10080

[1/8] Health check global............. PASS (status=ok)
[2/8] Chat dad......................... PASS (model=llama3.1:8b-instruct-q4_0)
[3/8] Chat child....................... PASS (model=llama3.2:3b-instruct-q4_0)
[4/8] Invalid user_id.................. PASS (HTTP 400)
[5/8] Learning submit.................. PASS (id=...)
[6/8] Learning status.................. PASS (status=pending)
[7/8] Voice no_speech.................. PASS (status=no_speech)
[8/8] Sidecar health directs........... PASS (3/3)

[smoke] Results: 8/8 passed
```

---

## Step 17 — Windows Client

```cmd
cd clients\windows
go build -o assistant-client.exe
assistant-client.exe
```

Open Microsoft Edge and navigate to `http://localhost:10090`.

---

## Step 18 — Graceful Shutdown

```bash
./scripts/stop_all.sh
```

---

## WSL2 Specifics

### Port access from Windows

WSL2 ports are automatically forwarded to Windows 11:

```
WSL :10080  →  Windows localhost:10080
WSL :10001  →  Windows localhost:10001
```

### ESP32 on the local network

The ESP32 must target the WSL IP, not `localhost`:

```bash
ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1
# e.g.: 172.29.45.123
```

Set up port forwarding from Windows if needed:

```powershell
# From Windows PowerShell (admin)
netsh interface portproxy add v4tov4 listenport=10080 listenaddress=0.0.0.0 connectport=10080 connectaddress=172.29.45.123
```

> **Note**: The WSL IP changes every time Windows restarts.

---

## Troubleshooting

### `nvidia-smi` fails in WSL

1. Update NVIDIA drivers on Windows (Game Ready 546+)
2. Run `wsl --shutdown` from PowerShell
3. Relaunch WSL and retry

### Ollama fails to start (systemd missing)

```bash
cat /etc/wsl.conf
# Must contain [boot] systemd=true
```

### Ollama starts but ignores the GPU

```bash
python3 -c "import torch; print(torch.cuda.is_available())"
# Must print True
```

### Slow I/O — sidecars timeout at startup

```bash
pwd   # must show /home/<user>/MyOwnJarvis — NOT /mnt/c/...
```

### Port not accessible from Windows

```powershell
Test-NetConnection -ComputerName localhost -Port 10080
# TcpTestSucceeded : True
```

If False, check Windows Firewall or restart WSL:

```powershell
wsl --shutdown
wsl -d Ubuntu-24.04
```

### `notify-send` silent

```bash
echo $DISPLAY          # must show :0 or similar
notify-send "Test" "Hello from WSL"
```

---

## Port Reference

| Component | WSL Port | Accessible from Windows |
|-----------|----------|------------------------|
| Go Orchestrator | 10080 | `localhost:10080` ✅ |
| Voice Sidecar | 10001 | `localhost:10001` ✅ |
| LLM Sidecar | 10002 | `localhost:10002` ✅ |
| Learning Sidecar | 10003 | `localhost:10003` ✅ |
| Windows Client | 10090 | `localhost:10090` ✅ |

---

## Daily Commands

```bash
# Start
cd ~/MyOwnJarvis && ./scripts/start_all.sh

# Smoke test
./scripts/smoke_test.sh

# Stop
./scripts/stop_all.sh

# Voice enrollment
cd sidecars/voice && source venv/bin/activate
python scripts/enroll_user.py --user dad --samples /mnt/c/Users/<you>/samples/*.wav

# Review pending corrections (Gate 3)
cd sidecars/learning && source venv/bin/activate
python scripts/review_learning.py list
python scripts/review_learning.py approve <id>

# Live logs
tail -f ~/MyOwnJarvis/logs/llm_sidecar.log
tail -f ~/MyOwnJarvis/logs/voice_sidecar.log
```

