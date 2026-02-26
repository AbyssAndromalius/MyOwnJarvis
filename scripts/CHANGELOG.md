# Changelog M5 - Corrections Code Review

## Version 1.1 (Post Code Review)

### 🐛 Bugs Corrigés

#### Bug 1: Commande de démarrage Python incorrecte
**Fichier:** `start_all.sh`  
**Ligne:** ~47

**Avant:**
```bash
python -m app.main >> "$log_file" 2>&1 &
```

**Après:**
```bash
uvicorn main:app --port "$port" >> "$log_file" 2>&1 &
```

**Raison:** Les sidecars M2, M3, M4 utilisent FastAPI/uvicorn et se démarrent avec `uvicorn main:app`, pas `python -m app.main` qui n'existe pas dans la structure du projet.

---

#### Bug 2: Incohérence des clés PID entre start et stop
**Fichiers:** `start_all.sh` et `stop_all.sh`

**Problème:**
- `start_all.sh` écrivait des clés avec espaces: `LLM Sidecar_PID=...`
- `stop_all.sh` lisait des clés avec underscores: `LLM_Sidecar_PID`
- Résultat: `stop_all.sh` ne trouvait jamais les PIDs, les processus restaient actifs

**Solution:** Convention harmonisée selon le cahier des charges

**Clés PID standardisées:**
```bash
LLM_PID=12345
VOICE_PID=12346
LEARNING_PID=12347
ORCHESTRATOR_PID=12348
```

**Changements dans `start_all.sh`:**
- Fonction `start_python_sidecar`: ajout d'un switch case pour mapper les noms de service aux clés PID simples
- Section d'affichage du résumé: mise à jour du pattern matching

**Changements dans `stop_all.sh`:**
- Section de parsing du fichier `pids.env`: mise à jour du pattern matching pour les nouvelles clés

---

## Validation

### ✅ Tests Passés
- [x] `start_all.sh` démarre les 4 composants avec les bonnes commandes
- [x] Les PIDs sont sauvegardés avec les clés harmonisées
- [x] `stop_all.sh` lit correctement les PIDs et arrête tous les processus
- [x] `smoke_test.sh` passe 8/8 tests (inchangé)

### 📋 Fichiers Modifiés
1. `start_all.sh` - Commande uvicorn + clés PID harmonisées
2. `stop_all.sh` - Clés PID harmonisées
3. `README.md` - Inchangé (exemples déjà corrects)

### 🎯 Impact
- **Critique:** Ces bugs empêchaient le système de démarrer et d'arrêter correctement
- **Correction:** Triviale (5 minutes)
- **Statut M5:** ✅ Validé après corrections

---

## Notes Techniques

### Pourquoi uvicorn ?
Les sidecars Python sont des applications FastAPI (ASGI) qui nécessitent un serveur ASGI comme uvicorn pour fonctionner. La commande standard est:
```bash
uvicorn main:app --port <PORT>
```

### Pourquoi des clés PID simples ?
- Plus lisible: `LLM_PID` vs `LLM_Sidecar_PID`
- Convention du cahier des charges M5
- Évite les problèmes d'espaces dans les noms de variables bash
- Plus facile à parser

### Structure attendue des sidecars
```
sidecars/llm/
├── main.py          # Point d'entrée FastAPI
├── app/
│   ├── __init__.py
│   └── ...
└── venv/            # Environnement virtuel (optionnel)
```

La commande `uvicorn main:app` :
- Cherche le fichier `main.py`
- Importe l'objet `app` (instance FastAPI)
- Démarre le serveur sur le port spécifié
