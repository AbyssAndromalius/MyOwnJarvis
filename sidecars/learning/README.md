# Learning Sidecar

Composant autonome pour gérer l'apprentissage supervisé à 3 gates pour l'assistant personnel Jarvis.

## Architecture

Le Learning Sidecar implémente un pipeline de validation en 3 étapes pour les corrections utilisateur :

```
Correction soumise
        │
        ▼
┌───────────────┐
│    GATE 1     │  Local LLM — sanity check
│ Cohérence +   │  "Est-ce cohérent ? Pas harmful ?"
│ Safety        │  → PASS / REJECT (automatique)
└──────┬────────┘
       │ PASS
       ▼
┌───────────────────────────────┐
│           GATE 2a             │  Local LLM — fact-check structuré
│  Fact-check local             │  Retourne {verdict, confidence (0-1)}
│  Personal info → auto-PASS    │  Si confidence ≥ 0.80 → PASS direct
└──────┬────────────────────────┘
       │ confidence < 0.80
       ▼
┌───────────────┐
│    GATE 2b    │  Claude API — fallback uniquement
│  Claude       │  Personal data NEVER sent
│  fact-check   │  → PASS / REJECT (automatique)
└──────┬────────┘
       │ PASS
       ▼
┌───────────────┐
│    GATE 3     │  Manuel — admin review CLI
│  Admin        │  Notification desktop déclenchée
│  approval     │  → APPROVE / REJECT
└──────┬────────┘
       │ APPROVE
       ▼
  Applied to Memory
  (POST http://localhost:10002/memory/add)
```

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Éditer `config.yaml` pour ajuster les paramètres :

- Port d'écoute (défaut: 10003)
- URL du LLM Sidecar (défaut: http://localhost:10002)
- Modèle Claude (défaut: claude-sonnet-4-20250514)
- Seuil de confiance Gate 2a (défaut: 0.80)
- Mots-clés d'information personnelle

Variables d'environnement :
- `ANTHROPIC_API_KEY` : Clé API Claude (optionnel, pour Gate 2b)

## Démarrage

```bash
uvicorn main:app --port 10003
```

Ou :

```bash
python main.py
```

## API Endpoints

### POST /learning/submit
Soumet une correction pour validation.

```json
{
  "user_id": "mom",
  "content": "La réunion du lundi est à 9h, pas 10h",
  "source": "user_correction"
}
```

Retourne immédiatement avec `status: "processing"` et traite en arrière-plan.

### GET /learning/status/{id}
Obtient l'état courant d'une correction.

### GET /learning/pending
Liste toutes les corrections en attente d'approbation admin.

### POST /learning/review/{id}
Approuve ou rejette une correction (admin uniquement).

```json
{
  "action": "approve",  // or "reject"
  "caller_id": "dad",
  "reason": "..."  // obligatoire si reject
}
```

### GET /health
Vérifie l'état du service et des dépendances.

## Script CLI Admin

Le script `scripts/review_learning.py` permet de reviewer les corrections :

```bash
# Lister les corrections en attente
python scripts/review_learning.py list

# Voir les détails d'une correction
python scripts/review_learning.py show <id>

# Approuver une correction
python scripts/review_learning.py approve <id>

# Rejeter une correction
python scripts/review_learning.py reject <id> --reason "Raison du rejet"
```

## Notifications Desktop

Quand une correction atteint Gate 3, une notification desktop est envoyée via `notify-send` (libnotify).

Si `notify-send` n'est pas disponible, le service continue sans crasher (log warning seulement).

## Stockage

Les corrections sont stockées dans `data/learning/` avec la structure suivante :

```
data/learning/
├── pending/    # En attente Gate 3
├── approved/   # Approuvé par admin
├── rejected/   # Rejeté à n'importe quel gate
└── applied/    # Confirmé appliqué à la mémoire
```

Chaque correction est un fichier JSON avec l'historique complet des gates.

## Tests

```bash
pytest tests/
```

Tous les tests utilisent des mocks pour les dépendances externes (LLM Sidecar, Claude API).

## Règles Importantes

1. **Personal Info** : Les corrections contenant des données personnelles (détectées par mots-clés) :
   - Passent Gate 2a automatiquement (confidence = 1.0)
   - Ne sont JAMAIS envoyées à Gate 2b (Claude API)

2. **Gate 2b Fallback** : Gate 2b n'est appelé que si :
   - Gate 2a confidence < 0.80 ET
   - Personal info = false

3. **Disponibilité** : Le service démarre même si :
   - LLM Sidecar est inaccessible
   - ANTHROPIC_API_KEY n'est pas configurée
   
   Gate 2b retourne `pass` avec `gate2b_unavailable` si Claude API est indisponible (pas de blocage indéfini).

4. **Autorisation Review** : Seuls `dad` et `mom` peuvent approuver/rejeter (vérification sur `caller_id`).

## Structure du Code

```
sidecars/learning/
├── main.py                        # FastAPI app, routes
├── pipeline.py                    # Orchestrateur Gates 1→2a→2b→3
├── gates/
│   ├── gate1_sanity.py            # Gate 1 — sanity check
│   ├── gate2a_local_factcheck.py  # Gate 2a — fact-check local
│   ├── gate2b_claude.py           # Gate 2b — Claude API
│   └── gate3_admin.py             # Gate 3 — admin approval
├── storage.py                     # Gestion fichiers JSON
├── notifier.py                    # Notifications desktop
├── config.py                      # Configuration + Pydantic
├── config.yaml                    # Fichier de config
├── requirements.txt
├── scripts/
│   └── review_learning.py         # CLI admin
└── tests/
    ├── test_pipeline.py           # Tests pipeline complet
    ├── test_gates.py              # Tests gates individuels
    ├── test_storage.py            # Tests stockage
    └── test_personal_info.py      # Tests détection personal info
```

## Dépendances

- **FastAPI** : Framework web asynchrone
- **httpx** : Client HTTP pour LLM Sidecar
- **anthropic** : SDK Claude API
- **rich** : CLI avec formatage (script review)
- **pytest** : Tests unitaires
