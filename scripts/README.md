# Scripts d'Intégration & Smoke Tests

Ce dossier contient les scripts pour démarrer, arrêter et tester le système complet de l'assistant personnel local.

## Prérequis

### Dépendances système
- **Obligatoires** :
  - `bash` (version 4+)
  - `curl`
  - `jq` (pour les smoke tests)
  - `go` (pour l'orchestrateur)
  - `python3` (pour les sidecars)

- **Optionnelles** (pour les tests audio) :
  - `sox` ou `ffmpeg`

### Installation de jq
```bash
# Debian/Ubuntu
sudo apt-get install jq

# macOS
brew install jq

# Fedora/RHEL
sudo dnf install jq
```

## Structure du Projet

```
local-llm-assistant/
├── scripts/
│   ├── start_all.sh      # Démarre tous les composants
│   ├── stop_all.sh       # Arrête tous les composants
│   ├── smoke_test.sh     # Valide le système
│   └── test_fixtures/    # Créé automatiquement
│       └── silence.wav
├── logs/                  # Créé automatiquement
│   ├── pids.env          # PIDs des processus
│   ├── orchestrator.log
│   ├── LLM Sidecar.log
│   ├── Voice Sidecar.log
│   └── Learning Sidecar.log
└── [autres répertoires du projet]
```

## Utilisation

### 1. Démarrer le Système

```bash
./scripts/start_all.sh
```

**Ordre de démarrage** :
1. LLM Sidecar (port 10002) - 🔥 Démarré en premier car dépendance des autres
2. Voice Sidecar (port 10001) - 🎤 Indépendant
3. Learning Sidecar (port 10003) - 📚 Dépend du LLM
4. Go Orchestrator (port 8080) - 🚀 Dernier, quand tout est prêt

**Sortie attendue** :
```
[start] Starting local LLM assistant system...

[start] Starting LLM Sidecar on :10002...
[start] LLM Sidecar ready (8s)
[start] Starting Voice Sidecar on :10001...
[start] Voice Sidecar ready (12s)
[start] Starting Learning Sidecar on :10003...
[start] Learning Sidecar ready (4s)
[start] Starting Go Orchestrator on :8080...
[start] Go Orchestrator ready (1s)

[ok] System started
  LLM Sidecar       PID=12345  :10002
  Voice Sidecar     PID=12346  :10001
  Learning Sidecar  PID=12347  :10003
  Go Orchestrator   PID=12348  :8080

[start] All services are running. Logs available in logs/
[start] To stop: ./scripts/stop_all.sh
```

**Comportement** :
- Chaque service a un health check avec retry (max 30s)
- Si un service ne démarre pas, le script s'arrête avec une erreur explicite
- Les PIDs sont sauvegardés dans `logs/pids.env`
- Les logs sont en mode append dans `logs/`

### 2. Arrêter le Système

```bash
./scripts/stop_all.sh
```

**Comportement** :
- Arrête les services dans l'ordre **inverse** du démarrage
- Envoie SIGTERM et attend 5 secondes
- Si le processus ne s'arrête pas, envoie SIGKILL
- Nettoie `logs/pids.env`

**Sortie attendue** :
```
[stop] Stopping local LLM assistant system...

[stop] Stopping Go Orchestrator (PID=12348)...
[stop] Go Orchestrator stopped gracefully
[stop] Stopping Learning Sidecar (PID=12347)...
[stop] Learning Sidecar stopped gracefully
[stop] Stopping Voice Sidecar (PID=12346)...
[stop] Voice Sidecar stopped gracefully
[stop] Stopping LLM Sidecar (PID=12345)...
[stop] LLM Sidecar stopped gracefully

[ok] All services stopped successfully
```

### 3. Lancer les Smoke Tests

**⚠️ Important** : Le système doit être démarré **avant** de lancer les tests.

```bash
./scripts/smoke_test.sh
```

**Tests effectués** (8 au total) :

| # | Test | Vérifie |
|---|------|---------|
| 1 | Health check global | Go Orchestrator répond et status=ok/degraded |
| 2 | Chat dad | Profil "dad" fonctionne, réponse non vide |
| 3 | Chat child | Profil "child" route vers modèle **3b** |
| 4 | Invalid user_id | user_id inconnu retourne HTTP 400 |
| 5 | Learning submit | Soumission d'apprentissage acceptée |
| 6 | Learning status | Status de l'apprentissage récupérable |
| 7 | Voice no_speech | Pipeline voix gère silence correctement |
| 8 | Sidecar health | Tous les sidecars répondent directement |

**Sortie attendue** :
```
[smoke] Starting smoke tests against http://localhost:8080

[1/8] Health check global.............. PASS (status=ok)
[2/8] Chat dad......................... PASS (model=llama3.1:8b-instruct-q4_0)
[3/8] Chat child....................... PASS (model=llama3.2:3b-instruct-q4_0)
[4/8] Invalid user_id.................. PASS (HTTP 400)
[5/8] Learning submit.................. PASS (id=abc123)
[6/8] Learning status.................. PASS (status=pending)
[7/8] Voice no_speech.................. PASS (status=no_speech)
[8/8] Sidecar health directs........... PASS (3/3)

[smoke] Results: 8/8 passed
```

**En cas d'échec** :
- Le test échoué affiche `FAIL` avec la raison
- La réponse HTTP complète est affichée pour debug
- Le script retourne un code d'erreur non-zéro

## Points Importants

### Environnements Virtuels Python
Les scripts activent automatiquement les venvs Python s'ils existent :
- `sidecars/llm/venv`
- `sidecars/voice/venv`
- `sidecars/learning/venv`

### Logs
- Les logs sont en mode **append** (ne sont pas écrasés)
- Chaque service a son propre fichier de log
- Pour nettoyer : `rm -f logs/*.log`

### Health Checks
- Chaque service expose `/health`
- Timeout de 30 secondes avec retry toutes les 2 secondes
- Si un service ne répond pas, le démarrage échoue explicitement

### Test du Classifier (Test 3)
Le test 3 est **critique** : il confirme que le classifier route correctement le profil `child` vers le modèle **3b** (plus rapide et adapté). C'est un test d'intégration qui valide :
- Le profil utilisateur est correctement chargé
- Le classifier analyse la complexité
- Le routage vers le bon modèle fonctionne

### Test Audio (Test 7)
Le test 7 requiert un fichier WAV de silence. Le script essaie dans cet ordre :
1. Générer avec `sox` si disponible
2. Générer avec `ffmpeg` si disponible
3. Copier depuis `sidecars/voice/tests/fixtures/silence.wav`

Si aucune méthode ne fonctionne, le test échoue avec un avertissement.

## Dépannage

### "jq is required but not installed"
```bash
sudo apt-get install jq
```

### "Go Orchestrator is not responding"
Le système n'est pas démarré. Lancez d'abord :
```bash
./scripts/start_all.sh
```

### "PID file not found"
Le système n'a pas été démarré avec `start_all.sh`. Vérifiez que `logs/pids.env` existe.

### Un service ne démarre pas
1. Vérifiez les logs dans `logs/<service>.log`
2. Vérifiez que le port n'est pas déjà utilisé : `lsof -i :<port>`
3. Vérifiez que les dépendances Python sont installées

### Test 3 échoue (modèle 3b non utilisé)
- Vérifiez la configuration du classifier dans l'orchestrateur
- Vérifiez les logs de l'orchestrateur
- Assurez-vous que le profil "child" existe avec la bonne configuration

## Workflow Typique

```bash
# 1. Démarrer le système
./scripts/start_all.sh

# 2. Vérifier que tout fonctionne
./scripts/smoke_test.sh

# 3. Développer / tester...

# 4. Arrêter proprement
./scripts/stop_all.sh
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│          Go Orchestrator (:8080)                    │
│   • Routage des requêtes                            │
│   • Gestion des profils                             │
│   • Coordination des sidecars                       │
└──────────────┬──────────────┬──────────────┬────────┘
               │              │              │
       ┌───────▼──────┐ ┌─────▼─────┐ ┌─────▼──────┐
       │ LLM Sidecar  │ │   Voice   │ │  Learning  │
       │   (:10002)   │ │  (:10001) │ │  (:10003)  │
       │              │ │           │ │            │
       │ • Classifier │ │ • STT     │ │ • Review   │
       │ • Generation │ │ • TTS     │ │ • Apply    │
       │ • Ollama     │ │ • VAD     │ │ • Filter   │
       └──────────────┘ └───────────┘ └────────────┘
```

## Conventions

- **Ports** :
  - 8080 : Go Orchestrator
  - 10001 : Voice Sidecar
  - 10002 : LLM Sidecar
  - 10003 : Learning Sidecar

- **Codes de retour** :
  - 0 : Succès
  - 1 : Erreur

- **Logs** :
  - Format : `[timestamp] [level] message`
  - Rotation non gérée (à implémenter si nécessaire)

## Licence

Voir le fichier LICENSE du projet principal.
