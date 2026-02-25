# Quick Start Guide - Learning Sidecar

## Installation (5 minutes)

### 1. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 2. Configurer (optionnel)

Pour utiliser Gate 2b avec Claude API :

```bash
cp .env.example .env
# Éditer .env et ajouter votre ANTHROPIC_API_KEY
```

**Note** : Le service fonctionne parfaitement sans API Claude. Gate 2b auto-passera avec "gate2b_unavailable".

### 3. Démarrer le service

```bash
./start.sh
```

Ou :

```bash
uvicorn main:app --port 10003
```

Le service écoute sur http://localhost:10003

## Test Rapide

### 1. Vérifier la santé du service

```bash
curl http://localhost:10003/health
```

Réponse attendue :
```json
{
  "status": "ok",
  "llm_sidecar": "unreachable",  // Normal si LLM Sidecar pas lancé
  "claude_api": "configured",
  "pending_count": 0,
  "storage": "ok"
}
```

### 2. Soumettre une correction

```bash
curl -X POST http://localhost:10003/learning/submit \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "mom",
    "content": "La réunion du lundi est à 9h, pas 10h"
  }'
```

Réponse :
```json
{
  "id": "abc-123-def...",
  "status": "processing"
}
```

### 3. Vérifier l'état

```bash
curl http://localhost:10003/learning/status/abc-123-def...
```

### 4. Lister les corrections en attente

Avec le CLI :
```bash
python scripts/review_learning.py list
```

Ou avec curl :
```bash
curl http://localhost:10003/learning/pending
```

### 5. Approuver une correction

```bash
python scripts/review_learning.py approve <id>
```

Ou avec curl :
```bash
curl -X POST http://localhost:10003/learning/review/<id> \
  -H "Content-Type: application/json" \
  -d '{
    "action": "approve",
    "caller_id": "dad"
  }'
```

## Tests

Lancer tous les tests :

```bash
./run_tests.sh
```

Ou :

```bash
pytest tests/ -v
```

## Scénarios de Test

### Scénario 1 : Correction Normale

1. Soumettre : "Le ciel est bleu"
2. Attendu : Gate 1 pass → Gate 2a pass (confiance élevée) → Gate 3 pending
3. Notification desktop envoyée
4. Approuver avec CLI

### Scénario 2 : Information Personnelle

1. Soumettre : "Ma fille s'appelle Alice"
2. Attendu : Gate 1 pass → Gate 2a auto-pass (personal info) → Gate 2b skippé → Gate 3 pending
3. Vérifier : `personal_info: true` dans le status

### Scénario 3 : Confiance Basse (Gate 2b)

**Note** : Nécessite le LLM Sidecar en cours d'exécution ou mockez les réponses

1. Soumettre une correction ambiguë
2. Attendu : Gate 1 pass → Gate 2a pass (confiance < 0.80) → Gate 2b appelé → Gate 3 pending

### Scénario 4 : Rejet

1. Soumettre du contenu harmful ou incohérent
2. Attendu : Gate 1 reject → final_status "rejected_gate1"

## Structure des Données

Les corrections sont stockées dans :

```
data/learning/
├── pending/    # En attente d'approbation admin
├── approved/   # Approuvé par admin
├── rejected/   # Rejeté à n'importe quel gate
└── applied/    # Appliqué à la mémoire
```

## Dépannage

### Le service ne démarre pas

- Vérifier Python 3.11+
- Vérifier les dépendances : `pip install -r requirements.txt`
- Vérifier le port 10003 n'est pas utilisé

### LLM Sidecar unreachable

C'est normal si le LLM Sidecar (localhost:10002) n'est pas lancé. Le Learning Sidecar démarre quand même, mais :
- Gate 1 retournera "error" 
- Gate 2a retournera "error"

Pour un test complet, lancez le LLM Sidecar ou mockez les réponses dans les tests.

### Claude API not configured

C'est normal et optionnel. Si ANTHROPIC_API_KEY n'est pas configurée :
- Gate 2b auto-passe avec "gate2b_unavailable"
- Le pipeline continue normalement

### Notifications ne s'affichent pas

- Vérifier que `notify-send` est installé : `which notify-send`
- Sur serveur sans GUI : normal, logs seulement
- Le service continue sans crasher même si notify-send absent

## Prochaines Étapes

1. Configurer le LLM Sidecar sur localhost:10002
2. Tester le pipeline complet avec vraies corrections
3. Configurer ANTHROPIC_API_KEY pour Gate 2b
4. Intégrer avec l'orchestrateur Go

## Support

Pour plus d'infos, voir [README.md](README.md)
