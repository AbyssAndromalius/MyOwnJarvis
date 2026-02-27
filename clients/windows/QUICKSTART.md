# Quick Start Guide - Windows Go Client

Guide de démarrage rapide pour le client Windows de l'assistant personnel.

## Installation Rapide

### 1. Prérequis
Assurez-vous d'avoir :
- ✅ Windows 11
- ✅ Go 1.22 ou supérieur installé ([télécharger Go](https://go.dev/dl/))
- ✅ **FFmpeg installé** (requis pour la conversion audio)
- ✅ Microsoft Edge (pour TTS Neural)
- ✅ L'orchestrateur Go tournant dans WSL2 sur le port 10080

### 2. Installation de FFmpeg (IMPORTANT)

**Le client nécessite FFmpeg pour convertir l'audio WebM (Edge) en WAV (Whisper).**

```bash
# Installation rapide via WinGet
winget install ffmpeg

# Vérification
ffmpeg -version
```

**Installation manuelle :**
1. Télécharger : [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Extraire dans `C:\ffmpeg`
3. Ajouter `C:\ffmpeg\bin` au PATH
4. Redémarrer le terminal

### 3. Vérification de Go
```bash
go version
```
Vous devriez voir : `go version go1.22.x windows/amd64` (ou supérieur)

### 3. Installation
```bash
# Naviguer dans le dossier du projet
cd windows-client

# Télécharger les dépendances
go mod download

# Compiler le projet
go build -o assistant-client.exe
```

Ou utilisez simplement le script fourni :
```bash
run.bat
```

## Premier Lancement

### Option 1 : Script automatique (recommandé)
```bash
run.bat
```
Le script :
- Crée automatiquement `config.yaml` s'il n'existe pas
- Compile le projet si nécessaire
- Lance le serveur

### Option 2 : Lancement manuel
```bash
./assistant-client.exe
```

## Accès à l'Interface

1. Le serveur démarre sur `http://127.0.0.1:10090`
2. Ouvrez **Microsoft Edge**
3. Naviguez vers `http://localhost:10090`
4. Vous devriez voir l'interface de l'assistant

## Utilisation

### Mode Vocal (Push-to-Talk)

**Avec la souris :**
1. Maintenez le bouton "🎙 Parler"
2. Parlez dans votre micro
3. Relâchez le bouton
4. Attendez la réponse

**Avec le clavier :**
1. Maintenez la touche **F12**
2. Parlez dans votre micro
3. Relâchez F12
4. Attendez la réponse

### Mode Texte

1. Sélectionnez votre profil (Dad, Mom, Teen, Child)
2. Tapez votre message dans le champ de saisie
3. Cliquez sur "Envoyer" ou appuyez sur Entrée

### Contrôles

- **Effacer l'historique** : Supprime tous les messages de la conversation
- **TTS Activé/Désactivé** : Active ou désactive la lecture vocale des réponses

## Vérification du Statut

### Indicateur dans l'interface
- 🟢 **Point vert** : Orchestrateur connecté ✓
- 🔴 **Point rouge** : Orchestrateur déconnecté ✗

### Test manuel
```bash
curl http://localhost:10090/api/health
```

Réponse attendue si OK :
```json
{
  "status": "ok",
  "orchestrator": "http://localhost:10080"
}
```

## Résolution de Problèmes Courants

### ❌ "Orchestrateur déconnecté"

**Cause** : L'orchestrateur WSL n'est pas démarré ou inaccessible

**Solution** :
1. Vérifiez que WSL2 est démarré
2. Lancez l'orchestrateur dans WSL : `./orchestrator`
3. Testez : `curl http://localhost:10080/health`

### ❌ "Impossible d'accéder au microphone"

**Cause** : Edge n'a pas la permission d'accéder au micro

**Solution** :
1. Dans Edge, cliquez sur l'icône de cadenas dans la barre d'adresse
2. Autorisez l'accès au microphone
3. Rechargez la page

### ❌ "Port 10090 déjà utilisé"

**Cause** : Une autre application utilise le port 10090

**Solution** :
```bash
# Trouvez le processus utilisant le port
netstat -ano | findstr :10090

# Tuez le processus (remplacez PID par l'ID trouvé)
taskkill /PID <PID> /F

# Ou changez le port dans config.yaml
```

### ❌ Le TTS ne fonctionne pas

**Cause** : Voix non disponibles ou navigateur incompatible

**Solution** :
1. Utilisez **Microsoft Edge** (pas Chrome ou Firefox)
2. Vérifiez les voix installées dans Windows
3. Testez avec : `edge://settings/voices`

### ❌ "Build failed"

**Cause** : Go n'est pas installé ou mal configuré

**Solution** :
```bash
# Vérifiez Go
go version

# Réinstallez les dépendances
go mod download
go mod verify

# Rebuild
go build -o assistant-client.exe
```

### ❌ "ffmpeg conversion failed"

**Cause** : FFmpeg n'est pas installé ou pas dans le PATH

**Solution** :
```bash
# Vérifier FFmpeg
ffmpeg -version

# Si erreur, installer :
winget install ffmpeg

# Ou ajouter au PATH manuellement :
# Rechercher "Variables d'environnement" dans Windows
# Éditer PATH → Ajouter C:\ffmpeg\bin
# Redémarrer le terminal
```

### ❌ "L'audio ne fonctionne pas"

**Cause** : Format WebM non converti

**Solution** :
1. Vérifier que FFmpeg est installé : `ffmpeg -version`
2. Regarder les logs du client Go pour les erreurs de conversion
3. Edge DevTools → Console → Vérifier le MIME type utilisé

## Configuration Avancée

Éditez `config.yaml` pour personnaliser :

```yaml
server:
  host: "127.0.0.1"    # Écoute locale uniquement
  port: 10090           # Port du serveur

orchestrator:
  url: "http://localhost:10080"  # URL de l'orchestrateur
  timeout_seconds: 60             # Timeout des requêtes

session:
  max_history: 20       # Messages max par session

tts:
  enabled: true         # Activer/désactiver TTS
  voice_preference:     # Voix préférées (dans l'ordre)
    - "Microsoft Aria Online (Natural) - English (United States)"
    - "Microsoft Guy Online (Natural) - English (United States)"
```

## Arrêt du Serveur

Appuyez sur **Ctrl+C** dans la fenêtre de commande pour un arrêt propre.

Le serveur :
1. Arrête d'accepter de nouvelles connexions
2. Termine les requêtes en cours (max 10 secondes)
3. Ferme proprement

## Prochaines Étapes

- 📖 Lisez le [README complet](README.md) pour plus de détails
- 🔧 Configurez vos préférences dans `config.yaml`
- 🎤 Testez différentes voix TTS dans Edge
- 📊 Consultez les logs pour le debugging

## Support

Pour les problèmes non couverts ici :
1. Vérifiez les logs dans la console
2. Testez les endpoints avec `curl`
3. Consultez le README.md pour plus de détails

## Checklist de Démarrage

- [ ] Go 1.22+ installé
- [ ] **FFmpeg installé et dans le PATH**
- [ ] Dépendances téléchargées (`go mod download`)
- [ ] Projet compilé (`go build`)
- [ ] Config.yaml présent
- [ ] Orchestrateur WSL démarré et accessible
- [ ] Port 10090 disponible
- [ ] Microsoft Edge installé
- [ ] Permissions microphone accordées
- [ ] Interface accessible sur http://localhost:10090

✅ Tout est bon ? Profitez de votre assistant personnel !
