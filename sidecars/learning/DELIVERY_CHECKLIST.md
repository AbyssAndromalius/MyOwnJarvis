# Learning Sidecar - Delivery Checklist

## ✅ Critères de Livraison

### Architecture & Configuration
- [x] FastAPI app sur port 10003
- [x] Configuration via config.yaml + Pydantic models
- [x] Démarrage propre même si LLM Sidecar absent
- [x] Démarrage propre même si ANTHROPIC_API_KEY absent
- [x] Logging structuré partout

### Endpoints API
- [x] `POST /learning/submit` - Soumet correction (retourne immédiatement, traite en background)
- [x] `GET /learning/status/{id}` - État temps réel d'une correction
- [x] `GET /learning/pending` - Liste corrections en attente Gate 3
- [x] `POST /learning/review/{id}` - Approuve/rejette (admin uniquement)
- [x] `GET /health` - Santé service + dépendances

### Pipeline 3 Gates
- [x] **Gate 1** : Sanity check via LLM Sidecar
  - Vérifie cohérence et safety
  - Retourne JSON {verdict, reason}
  - Gère timeout/erreur → status "error"
  
- [x] **Gate 2a** : Fact-check local via LLM Sidecar
  - Retourne {verdict, confidence, reason}
  - Détection auto personal info → auto-pass confidence 1.0
  - Si confidence ≥ 0.80 → skip Gate 2b
  
- [x] **Gate 2b** : Claude API fallback
  - Appelé seulement si confidence < 0.80 ET personal_info=false
  - JAMAIS d'info personnelle envoyée
  - Auto-pass si API indisponible → "gate2b_unavailable"
  
- [x] **Gate 3** : Admin approval
  - Stockage dans data/learning/pending/
  - Notification desktop notify-send
  - CLI review pour admin

### Détection Personal Info
- [x] Keywords configurables (s'appelle, prénom, habite, etc.)
- [x] Bypass Gate 2a sans appel LLM
- [x] Jamais envoyé à Gate 2b (Claude API)
- [x] Flag `personal_info: true` dans correction

### Stockage
- [x] Structure data/learning/{pending,approved,rejected,applied}
- [x] Format JSON avec historique complet
- [x] Transitions d'état automatiques
- [x] Fichiers bougent entre dossiers selon status

### Script CLI
- [x] `review_learning.py list` - Liste pending
- [x] `review_learning.py show <id>` - Détails correction
- [x] `review_learning.py approve <id>` - Approuve
- [x] `review_learning.py reject <id> --reason` - Rejette
- [x] Affichage formaté avec rich
- [x] Vérification caller_id (dad/mom uniquement)

### Notifications
- [x] notify-send appelé à l'arrivée en Gate 3
- [x] Ne crashe pas si notify-send absent
- [x] Log warning si indisponible

### Application à la Mémoire
- [x] POST http://localhost:10002/memory/add après approbation
- [x] Stockage memory_id retourné
- [x] Transition vers status "applied"

### Tests
- [x] `test_pipeline.py` - Pipeline complet avec mocks
- [x] `test_gates.py` - Chaque gate individuellement
- [x] `test_storage.py` - Stockage et transitions
- [x] `test_personal_info.py` - Détection keywords
- [x] Tous mocks (pas de vraie dépendance externe)
- [x] pytest.ini configuré
- [x] Exécutable via `./run_tests.sh` ou `pytest tests/`

### Gestion d'Erreurs
- [x] Toutes les erreurs retournent JSON structuré
- [x] HTTP status codes appropriés (404, 400, 403)
- [x] Timeout gérés (LLM Sidecar, Claude API)
- [x] Parsing JSON robuste (avec/sans markdown backticks)

### Code Quality
- [x] Type hints partout
- [x] Commentaires en anglais
- [x] Docstrings pour fonctions publiques
- [x] Structure modulaire (gates/, storage, notifier, pipeline)
- [x] requirements.txt complet

### Documentation
- [x] README.md complet
- [x] QUICKSTART.md pour démarrage rapide
- [x] Commentaires inline pour logique complexe
- [x] .env.example pour configuration

### Scripts Utilitaires
- [x] start.sh - Démarre service
- [x] run_tests.sh - Lance tests
- [x] Scripts exécutables (chmod +x)

## 🎯 Fonctionnalités Clés

### Robustesse
- ✅ Démarre même sans LLM Sidecar
- ✅ Démarre même sans Claude API key
- ✅ Gates retournent "error" si dépendance indisponible
- ✅ Gate 2b auto-pass si Claude API down (pas de blocage)

### Sécurité
- ✅ Personal info JAMAIS envoyée à Claude API
- ✅ Vérification caller_id sur review endpoints
- ✅ Safety check dans Gate 1

### Performance
- ✅ Pipeline asynchrone (background tasks)
- ✅ Submit retourne immédiatement
- ✅ Status endpoint pour polling

### UX Admin
- ✅ CLI riche et coloré
- ✅ Notifications desktop
- ✅ Détails complets via `show` command

## 📋 Commandes de Vérification

```bash
# 1. Tests passent
pytest tests/ -v

# 2. Service démarre
uvicorn main:app --port 10003

# 3. Health check OK
curl http://localhost:10003/health

# 4. Submit correction
curl -X POST http://localhost:10003/learning/submit \
  -H "Content-Type: application/json" \
  -d '{"user_id":"mom","content":"Test"}'

# 5. CLI fonctionne
python scripts/review_learning.py list
```

## 🚀 Prêt pour Livraison

Tous les critères sont remplis. Le Learning Sidecar est :
- ✅ Complet
- ✅ Testé
- ✅ Documenté
- ✅ Robuste
- ✅ Prêt pour intégration

## 📦 Fichiers Livrés

Total : 25 fichiers

```
learning_sidecar/
├── README.md                       # Documentation complète
├── QUICKSTART.md                   # Guide démarrage rapide
├── DELIVERY_CHECKLIST.md          # Cette checklist
├── config.yaml                    # Configuration
├── config.py                      # Modèles Pydantic
├── main.py                        # FastAPI app
├── pipeline.py                    # Orchestrateur
├── storage.py                     # Gestion fichiers
├── notifier.py                    # Notifications
├── requirements.txt               # Dépendances
├── pytest.ini                     # Config tests
├── .gitignore                     # Git
├── .env.example                   # Template env
├── start.sh                       # Script démarrage
├── run_tests.sh                   # Script tests
├── gates/
│   ├── __init__.py
│   ├── gate1_sanity.py            # Gate 1
│   ├── gate2a_local_factcheck.py  # Gate 2a
│   ├── gate2b_claude.py           # Gate 2b
│   └── gate3_admin.py             # Gate 3
├── scripts/
│   └── review_learning.py         # CLI admin
└── tests/
    ├── __init__.py
    ├── test_pipeline.py           # Tests pipeline
    ├── test_gates.py              # Tests gates
    ├── test_storage.py            # Tests storage
    └── test_personal_info.py      # Tests personal info
```
