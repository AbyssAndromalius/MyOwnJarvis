# MyOwnJarvis — Assistant Personnel Local

Assistant personnel familial fonctionnant entièrement en local. Go orchestrator + 3 sidecars Python FastAPI + Ollama LLM + identification vocale.

Conçu pour une famille de 4 (dad, mom, teen, child) avec des profils de sécurité et des modèles adaptés à chaque utilisateur.

## Architecture

```
POST /voice (ESP32 WAV)          POST /chat (texte)        POST /learn
        │                               │                       │
        └───────────────────────────────┘                       │
                        │                                       │
              Go Orchestrator :8080                             │
                        │                                       │
        ┌───────────────┼───────────────┐                       │
        │               │               │                       │
Voice Sidecar    LLM Sidecar    Learning Sidecar ───────────────┘
  :10001           :10002           :10003
  FastAPI          FastAPI          FastAPI
  Whisper          Ollama           Gates 1→3
  Resemblyzer      ChromaDB         Claude API (fallback)
```

**Flux vocal :** WAV → VAD (Silero) → Speaker ID (Resemblyzer) → Transcription (Whisper) → Classification → LLM → Réponse

**Flux texte :** user_id + message → Classification heuristique → Mémoire ChromaDB → LLM (3B ou 8B) → Réponse

**Flux learning :** correction → Gate 1 (sanity) → Gate 2a (fact-check local) → Gate 2b (Claude si confidence < 0.80) → Gate 3 (approbation admin) → Mémoire

## Prérequis

### Système

- **OS :** Ubuntu 24.04 (ou Linux compatible)
- **GPU :** NVIDIA avec ≥ 12 GB VRAM (RTX 4070 Ti Super 16GB recommandé)
- **Go :** 1.22+
- **Python :** 3.11+
- **CUDA :** toolkit compatible avec PyTorch 2.x
- **Ollama :** installé et fonctionnel (`curl http://localhost:11434/api/tags`)

### Outils système

```bash
sudo apt install jq sox curl
```

`jq` et `curl` sont nécessaires pour le smoke test. `sox` permet de générer le fichier silence.wav de test.

## Premier lancement — Guide pas à pas

### 1. Cloner et se placer dans le projet

```bash
git clone https://github.com/AbyssAndromalius/MyOwnJarvis.git
cd MyOwnJarvis
```

### 2. Télécharger les modèles Ollama

```bash
ollama pull llama3.2:3b-instruct-q4_0    # ~2 GB — modèle rapide (child/teen/simple)
ollama pull llama3.1:8b-instruct-q4_0     # ~5 GB — modèle complet (admin/complexe)
```

Vérifier qu'ils sont disponibles :

```bash
ollama list
```

### 3. Installer les dépendances Go

```bash
go mod download
go mod verify
```

### 4. Créer les environnements Python

Chaque sidecar a son propre `requirements.txt`. On recommande un venv par sidecar :

```bash
# LLM Sidecar
cd sidecars/llm
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Voice Sidecar
cd ../voice
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Learning Sidecar
cd ../learning
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

cd ../..
```

> **Note :** Le voice sidecar nécessite PyTorch avec CUDA. Si `torch` ne détecte pas votre GPU, installez la version CUDA manuellement : `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121`

### 5. Initialiser les répertoires de données

```bash
chmod +x scripts/*.sh
./scripts/init_data.sh
```

Cela crée l'arborescence `data/` attendue par les sidecars :

```
data/
├── voice/
│   ├── embeddings/       ← speaker embeddings après enrollment
│   └── access_logs/      ← logs d'identification vocale
├── memory/               ← ChromaDB (mémoire persistante)
└── learning/
    ├── pending/          ← corrections en attente
    ├── approved/         ← corrections validées
    ├── rejected/         ← corrections rejetées
    └── applied/          ← corrections appliquées
```

### 6. (Optionnel) Configurer Claude API pour Gate 2b

Si vous souhaitez que le learning sidecar utilise Claude comme fallback de fact-checking :

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Sans cette clé, Gate 2b auto-passe (le système reste fonctionnel, seul le fact-check externe est désactivé).

### 7. Démarrer le système

```bash
./scripts/start_all.sh
```

Le script démarre les services dans l'ordre : init_data → LLM → Voice → Learning → Go Orchestrator, en attendant le health check de chacun avant de passer au suivant.

Sortie attendue :

```
[start] Starting local LLM assistant system...
[start] Initializing data directories...
  ✓ All data directories already exist
[start] Starting LLM Sidecar on :10002...
[start] LLM Sidecar ready (4s)
[start] Starting Voice Sidecar on :10001...
[start] Voice Sidecar ready (8s)
[start] Starting Learning Sidecar on :10003...
[start] Learning Sidecar ready (2s)
[start] Starting Go Orchestrator on :8080...
[start] Go Orchestrator ready (1s)

[ok] System started
  LLM Sidecar       PID=12345  :10002
  Voice Sidecar     PID=12346  :10001
  Learning Sidecar  PID=12347  :10003
  Go Orchestrator   PID=12348  :8080
```

> **Note :** Le Voice Sidecar peut prendre 10-20s au premier lancement (chargement de Whisper + Resemblyzer). Si le GPU n'est pas disponible, le script continue sans le voice sidecar — le chat texte et le learning restent fonctionnels.

### 8. Valider avec le smoke test

```bash
./scripts/smoke_test.sh
```

Tests exécutés :

| # | Test | Vérifie |
|---|------|---------|
| 1 | Health check global | Orchestrator + 3 sidecars |
| 2 | Chat dad | Routing → LLM → réponse |
| 3 | Chat child | Routing → modèle 3B |
| 4 | Invalid user_id | Rejet HTTP 400 |
| 5 | Learning submit | Pipeline de correction |
| 6 | Learning status | Suivi de correction |
| 7 | Voice no_speech | Pipeline vocale (silence) |
| 8 | Sidecar health directs | Santé individuelle |

Résultat attendu : **8/8 passed**.

### 9. Arrêter le système

```bash
./scripts/stop_all.sh
```

## Enrollment vocal

Avant d'utiliser la reconnaissance vocale, chaque membre de la famille doit enregistrer son profil :

```bash
cd sidecars/voice
source venv/bin/activate

# Enregistrer papa avec 3-5 échantillons WAV de sa voix
python scripts/enroll_user.py --user dad --samples /path/to/dad_sample1.wav /path/to/dad_sample2.wav /path/to/dad_sample3.wav

# Répéter pour chaque membre
python scripts/enroll_user.py --user mom --samples ...
python scripts/enroll_user.py --user teen --samples ...
python scripts/enroll_user.py --user child --samples ...

deactivate
```

Les embeddings sont sauvés dans `data/voice/embeddings/`. Après enrollment, on peut hot-reload sans redémarrer :

```bash
curl -X POST http://localhost:10001/voice/reload-embeddings
```

## API Endpoints

### POST /chat — Conversation texte

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "dad", "message": "Explique TCP vs UDP", "conversation_history": []}'
```

Réponse :

```json
{
  "response": "...",
  "model_used": "llama3.1:8b-instruct-q4_0",
  "memories_used": ["..."],
  "user_id": "dad"
}
```

### POST /voice — Conversation vocale

```bash
curl -X POST http://localhost:8080/voice -F "file=@audio.wav"
```

Réponses possibles : `identified`, `fallback`, `no_speech`, `rejected`.

### POST /learn — Soumettre une correction

```bash
curl -X POST http://localhost:8080/learn \
  -H "Content-Type: application/json" \
  -d '{"user_id": "dad", "content": "Le serveur de prod est sur Ubuntu 24.04", "source": "user_correction"}'
```

### GET /health — État du système

```bash
curl http://localhost:8080/health
```

Statuts : `ok` (tous les sidecars répondent), `degraded` (au moins un absent), `error` (tous absents).

## Profils utilisateurs

| Profil | Rôle | Modèle | Restrictions |
|--------|------|--------|-------------|
| dad | admin | auto (3B/8B) | Aucune |
| mom | admin | auto (3B/8B) | Aucune |
| teen | user | 3B forcé | Pas de contenu adulte ni conseil financier |
| child | user | 3B forcé | Uniquement devoirs, histoires, jeux, science enfants |

Les admins peuvent reviewer les corrections learning (`POST /learning/review/{id}`) et supprimer des mémoires.

## Structure du projet

```
MyOwnJarvis/
├── cmd/assistant/main.go          # Point d'entrée Go
├── internal/                      # Go orchestrator (handlers, clients, config, server)
├── sidecars/
│   ├── llm/                       # LLM Sidecar (Ollama + ChromaDB + classifier)
│   ├── voice/                     # Voice Sidecar (VAD + Speaker ID + Whisper)
│   └── learning/                  # Learning Sidecar (3 gates + storage)
├── scripts/
│   ├── init_data.sh               # Initialise data/
│   ├── start_all.sh               # Démarre tout le système
│   ├── stop_all.sh                # Arrête tout le système
│   └── smoke_test.sh              # Tests de validation (8 tests)
├── configs/
│   ├── assistant.yaml             # Config de référence (non lu par le code)
│   └── user_profiles.yaml         # Profils détaillés (référence)
├── config.yaml                    # Config Go orchestrator
└── data/                          # Créé par init_data.sh (gitignored)
    ├── voice/embeddings/
    ├── memory/
    └── learning/
```

## VRAM estimée

| Configuration | VRAM |
|---|---|
| 3B seul | ~3.3 GB |
| 8B seul | ~5.5 GB |
| 3B + 8B chargés | ~9.3 GB |
| + Whisper medium | ~10.8 GB |
| + Coqui TTS (futur) | ~11.3 GB |

## Dépannage

### Le Go orchestrator ne démarre pas

Vérifier que `config.yaml` est à la racine du projet et que le script est lancé depuis la racine :

```bash
ls config.yaml       # doit exister
./scripts/start_all.sh
```

Consulter les logs :

```bash
cat logs/orchestrator.log
```

### Le LLM sidecar ne démarre pas

Vérifier qu'Ollama tourne et que les modèles sont téléchargés :

```bash
curl http://localhost:11434/api/tags
ollama list
```

Consulter les logs :

```bash
cat logs/LLM_Sidecar.log
```

### Le Voice sidecar échoue

Le voice sidecar nécessite CUDA. Vérifier :

```bash
python3 -c "import torch; print(torch.cuda.is_available())"
```

Le système fonctionne sans le voice sidecar — seul `/voice` sera indisponible, `/chat` et `/learn` restent opérationnels.

### Le smoke test échoue sur le test 6 (Learning status)

Normal si le LLM Sidecar est lent au premier appel (chargement du modèle). Le test 5 soumet une correction traitée en arrière-plan par les gates — le test 6 peut arriver avant que la pipeline finisse. Relancer le smoke test une seconde fois.

### Port déjà occupé

```bash
lsof -i :8080    # ou 10001, 10002, 10003
./scripts/stop_all.sh
```

## Décisions d'architecture

| Sujet | Décision |
|-------|----------|
| IPC | HTTP/REST local entre Go et sidecars FastAPI |
| Model routing | Heuristique (profil + longueur + keywords) → 3B ou 8B |
| Push-to-talk | REST API — compatible ESP32 |
| Voice mismatch | Fallback hiérarchique child > teen > mom > dad (0.60–0.74) |
| Mémoire | ChromaDB, collection isolée par utilisateur |
| Gate 2 | LLM local d'abord, Claude API si confidence < 0.80 |
| Personal data | Jamais envoyé à Claude (filtre keywords) |
| Abliteration | Parkée — future admin-only, modèle séparé |

## Licence

Projet interne — pas de distribution publique.
