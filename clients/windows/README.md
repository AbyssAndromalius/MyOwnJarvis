# Windows Go Client - Assistant Personnel Local

Client Windows léger en Go pour un assistant personnel vocal. Sert une interface web push-to-talk et communique avec un orchestrateur Go tournant dans WSL2.

## Architecture

```
Edge Browser (localhost:10090)
      │
      ├── Push-to-talk (bouton / F12)
      ├── Capture audio WAV
      ├── POST /api/voice → Windows Go Client
      │                           │
      │                    POST localhost:10080/voice (WSL Orchestrator)
      │                           │
      │                    ← JSON Response
      │
      └── Affichage + TTS (Web Speech API)
```

## Fonctionnalités

### Interface Push-to-Talk
- **Bouton souris** : Maintenez "🎙 Parler" pour enregistrer, relâchez pour envoyer
- **Touche F12** : Même comportement via clavier
- **Indicateur visuel** : Animation pulse pendant l'enregistrement
- **Protection** : Désactivation pendant le traitement (évite les double-envois)

### Historique de Conversation
- Fil de messages style chat
- Affichage : transcription + réponse + user_id + modèle utilisé
- Statuts spéciaux : `no_speech`, `rejected`, `fallback`
- Bouton "Effacer l'historique"
- Conservation en mémoire par session (max 20 échanges)

### Text-to-Speech (TTS)
- Web Speech API avec voix Edge Neural
- Lecture automatique des réponses
- Priorité des voix :
  1. Microsoft Aria Online (Natural)
  2. Microsoft Guy Online (Natural)
  3. Première voix fr-FR disponible
  4. Première voix disponible
- Bouton pour activer/désactiver

### Mode Texte
- Champ de saisie + sélecteur user_id
- Envoi via `POST /api/chat`
- Utile quand la reconnaissance vocale n'est pas disponible

### Health Check
- Vérification automatique de l'orchestrateur (toutes les 30s)
- Indicateur visuel du statut de connexion
- Bannière d'avertissement si déconnecté
- Le client démarre même si l'orchestrateur est absent

## API Endpoints

### `GET /`
Sert la page HTML de l'interface.

### `POST /api/voice`
Reçoit un fichier WAV multipart, le forward à l'orchestrateur.

**Request:**
```
multipart/form-data:
  - audio: fichier WAV
```

**Response:**
```json
{
  "status": "identified",
  "user_id": "dad",
  "confidence": 0.87,
  "transcript": "Quelle heure est-il ?",
  "response": "Il est 14h30.",
  "fallback": false,
  "model_used": "gpt-4"
}
```

Autres statuts possibles :
- `no_speech` : Aucune parole détectée
- `rejected` : Identification rejetée (confiance trop faible)

### `POST /api/chat`
Mode texte direct.

**Request:**
```json
{
  "user_id": "dad",
  "message": "Bonjour"
}
```

**Response:**
```json
{
  "response": "Bonjour ! Comment puis-je vous aider ?",
  "model_used": "gpt-4",
  "user_id": "dad"
}
```

### `GET /api/health`
Vérifie que l'orchestrateur WSL est joignable.

**Response:**
```json
{
  "status": "ok",
  "orchestrator": "http://localhost:10080"
}
```

Ou si déconnecté :
```json
{
  "status": "orchestrator_unreachable",
  "orchestrator": "http://localhost:10080",
  "detail": "connection refused"
}
```

### `POST /api/clear-history`
Efface l'historique de conversation pour la session actuelle.

**Response:**
```json
{
  "status": "ok"
}
```

## Installation

### Prérequis
- Windows 11
- Go 1.22+
- Microsoft Edge (pour les voix Neural TTS)
- **FFmpeg** (pour la conversion audio WebM → WAV)
- Orchestrateur Go tournant dans WSL2 sur `localhost:10080`

### Installation de FFmpeg
Le client nécessite FFmpeg pour convertir l'audio WebM (format natif d'Edge) en WAV (requis par Whisper).

**Installation via WinGet (recommandé) :**
```bash
winget install ffmpeg
```

**Installation manuelle :**
1. Télécharger depuis [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Extraire dans `C:\ffmpeg`
3. Ajouter `C:\ffmpeg\bin` au PATH Windows
4. Vérifier : `ffmpeg -version`

**Note :** Le client démarrera sans FFmpeg, mais les enregistrements vocaux échoueront.

### Installation des dépendances
```bash
go mod download
```

### Configuration
Éditez `config.yaml` :

```yaml
server:
  host: "127.0.0.1"
  port: 10090

orchestrator:
  url: "http://localhost:10080"
  timeout_seconds: 60

session:
  max_history: 20

tts:
  enabled: true
  voice_preference:
    - "Microsoft Aria Online (Natural) - English (United States)"
    - "Microsoft Guy Online (Natural) - English (United States)"
```

## Utilisation

### Compilation
```bash
go build -o assistant-client.exe
```

### Démarrage
```bash
./assistant-client.exe
```

Le client démarre sur `http://127.0.0.1:10090`

**Logs de démarrage :**
```
Starting Windows Go Client on 127.0.0.1:10090
Orchestrator URL: http://localhost:10080
Open http://127.0.0.1:10090 in Microsoft Edge to use the assistant
Orchestrator health check passed
```

Si l'orchestrateur n'est pas disponible :
```
WARNING: Orchestrator is not reachable at http://localhost:10080
         The client will start anyway, but voice/chat features won't work until the orchestrator is available
```

### Accès à l'interface
Ouvrez Microsoft Edge et naviguez vers :
```
http://localhost:10090
```

### Arrêt gracieux
Appuyez sur `Ctrl+C` pour un arrêt propre du serveur.

## Gestion des Sessions

- Chaque utilisateur reçoit un cookie de session (`session_id`)
- L'historique de conversation est maintenu en mémoire par session
- Taille maximale : 20 derniers échanges (FIFO)
- Nettoyage automatique des sessions inactives (> 24h) toutes les heures
- **Pas de persistance** : l'historique est perdu au redémarrage

## Structure du Projet

```
clients/windows/
├── main.go              # Point d'entrée, démarrage serveur
├── config.go            # Chargement config.yaml
├── handlers.go          # Handlers HTTP
├── session.go           # Gestion sessions et historique
├── proxy.go             # Communication avec orchestrateur WSL
├── templates/
│   └── index.html       # Interface push-to-talk complète
├── config.yaml          # Configuration
├── go.mod               # Dépendances Go
└── README.md            # Documentation
```

## Dépendances

- **Standard Library** : `net/http`, `html/template`, `encoding/json`, `embed`
- **Externe** : `gopkg.in/yaml.v3` (configuration YAML)

Aucune dépendance externe lourde. Le client reste léger et portable.

## Sécurité

- Écoute uniquement sur `127.0.0.1` (pas d'exposition réseau)
- Sessions HTTP-only cookies
- SameSite=Strict pour les cookies
- Timeouts configurés pour toutes les requêtes HTTP
- Pas d'exécution de code arbitraire côté serveur
- Le WAV est forwardé tel quel, pas de traitement côté client

## Limitations Connues

- L'historique n'est pas persisté (perdu au redémarrage)
- Une seule session par navigateur (cookie-based)
- Le format audio doit être WAV compatible avec l'orchestrateur
- Nécessite Edge pour les meilleures voix TTS Neural

## Résolution de Problèmes

### L'orchestrateur n'est pas joignable
- Vérifiez que l'orchestrateur WSL tourne sur `localhost:10080`
- Testez manuellement : `curl http://localhost:10080/health`
- Le client peut démarrer sans orchestrateur, mais les fonctionnalités seront limitées

### Le microphone ne fonctionne pas
- Vérifiez les permissions du navigateur
- Edge doit avoir accès au microphone
- Testez avec `navigator.mediaDevices.getUserMedia({ audio: true })`

### Le TTS ne fonctionne pas
- Utilisez Microsoft Edge pour les voix Neural
- Vérifiez que les voix sont installées : `window.speechSynthesis.getVoices()`
- La synthèse peut prendre quelques secondes au premier lancement

### Port 10090 déjà utilisé
- Modifiez le port dans `config.yaml`
- Ou arrêtez le processus utilisant le port : `netstat -ano | findstr :10090`

### FFmpeg non trouvé
**Erreur :** `ffmpeg conversion failed: exec: "ffmpeg": executable file not found`

**Causes :**
- FFmpeg n'est pas installé
- FFmpeg n'est pas dans le PATH

**Solutions :**
```bash
# Vérifier FFmpeg
ffmpeg -version

# Installer via WinGet
winget install ffmpeg

# Ou ajouter manuellement au PATH
# Rechercher "Variables d'environnement" → Modifier PATH → Ajouter C:\ffmpeg\bin
```

**Après installation :**
- Redémarrer le terminal
- Relancer le client Go

## Performance

- Démarrage : < 1 seconde
- Mémoire : ~10-20 MB (dépend du nombre de sessions actives)
- Latence réseau : Dépend de l'orchestrateur WSL
- Pas de limite de débit côté client (géré par l'orchestrateur)

## Développement

### Tests manuels
```bash
# Health check
curl http://localhost:10090/api/health

# Envoi texte
curl -X POST http://localhost:10090/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"dad","message":"Bonjour"}'
```

### Logs
Le client affiche des logs sur stdout :
- Démarrage/arrêt
- Health check orchestrateur
- Erreurs de templates ou de handlers

### Rebuild rapide
```bash
go build && ./assistant-client.exe
```

## Licence

Projet interne. Tous droits réservés.
