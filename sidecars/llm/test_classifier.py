"""
Unit tests for the heuristic query classifier.
No Ollama or ChromaDB required — purely logic tests.

Run with: pytest tests/test_classifier.py -v
"""
from __future__ import annotations

import sys
import os

# Allow imports from parent directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from classifier import HeuristicClassifier, ClassificationResult
from config import load_config

# Use the real config.yaml
_config = load_config()
_clf = HeuristicClassifier(_config)


def classify(user_id: str, message: str) -> ClassificationResult:
    return _clf.classify(user_id, message)


# ---------------------------------------------------------------------------
# Test cases — documented for /classifier/explain validation
# ---------------------------------------------------------------------------

class TestProfileOverride:
    """Profile-level rules have highest priority."""

    def test_teen_short_message_is_fast(self):
        """CASE 1: teen profile overrides any length rule → fast"""
        result = classify("teen", "bonjour")
        assert result.model_key == "fast"
        assert "teen" in result.reason

    def test_teen_long_complex_message_still_fast(self):
        """CASE 2: teen + long complexity message → still fast (profile wins)"""
        long_msg = "Peux-tu m'expliquer en détail comment fonctionne un moteur à combustion interne et quelles sont les différences avec les moteurs électriques modernes ?"
        result = classify("teen", long_msg)
        assert result.model_key == "fast"
        assert "teen" in result.reason

    def test_child_profile_is_fast(self):
        """CASE 3: child profile always → fast"""
        result = classify("child", "Raconte-moi une histoire")
        assert result.model_key == "fast"

    def test_dad_with_no_preference_uses_rules(self):
        """CASE 4: dad has no forced preference — classifier rules apply"""
        # Short message → should hit length rule → fast
        result = classify("dad", "Bonjour !")
        # "bonjour" is a conversational keyword → fast
        assert result.model_key == "fast"

    def test_mom_with_no_preference_uses_rules(self):
        """CASE 5: mom has no forced preference — complexity keyword → full"""
        result = classify("mom", "Explique-moi comment fonctionne la blockchain")
        assert result.model_key == "full"
        assert "explique" in result.reason or "comment fonctionne" in result.reason


class TestConversationalKeywords:
    """Conversational keywords trigger fast model."""

    @pytest.mark.parametrize("word", [
        "bonjour", "merci", "salut", "hello", "thanks", "ok",
        "oui", "non", "quoi", "c'est quoi", "c'est qui",
    ])
    def test_conversational_keyword(self, word: str):
        result = classify("dad", f"Dis-moi {word} pour savoir")
        assert result.model_key == "fast"

    def test_hello_in_sentence(self):
        result = classify("mom", "hello, how are you?")
        assert result.model_key == "fast"


class TestComplexityKeywords:
    """Complexity keywords trigger full model for non-forced profiles."""

    @pytest.mark.parametrize("phrase", [
        "explique", "analyse", "compare", "pourquoi",
        "comment fonctionne", "quelle est la différence",
        "pros and cons", "débat",
    ])
    def test_complexity_keyword_for_dad(self, phrase: str):
        result = classify("dad", f"Peux-tu {phrase} ce concept pour moi ?")
        assert result.model_key == "full"

    def test_complexity_keyword_for_mom(self):
        result = classify("mom", "Analyse les avantages et inconvénients de ce choix")
        assert result.model_key == "full"


class TestLengthRules:
    """Length-based fallback rules (when no profile override or keyword match)."""

    def test_short_message_fast(self):
        """Less than 15 words and no keyword → fast"""
        result = classify("dad", "Quelle heure est-il aujourd'hui ?")
        assert result.model_key == "fast"

    def test_long_message_full(self):
        """More than 30 words with no keyword → full"""
        # 32 word message with no keywords
        long = ("Lorem ipsum dolor sit amet consectetur adipiscing elit sed do "
                "eiusmod tempor incididunt ut labore et dolore magna aliqua ut "
                "enim ad minim veniam quis nostrud exercitation ullamco laboris "
                "nisi aliquip commodo")
        words = long.split()
        assert len(words) > 30, f"Need >30 words, got {len(words)}"
        result = classify("dad", long)
        assert result.model_key == "full"

    def test_medium_message_default_fast(self):
        """Between 15-30 words, no keyword → default fast"""
        medium = "Je veux savoir si tu peux m'aider avec mon projet scolaire sur les planètes du système solaire"
        words = medium.split()
        assert 15 <= len(words) <= 30, f"Should be 15-30 words, got {len(words)}"
        result = classify("dad", medium)
        assert result.model_key == "fast"


class TestClassifierExplainCases:
    """
    5 documented test cases for /classifier/explain validation.
    """

    def test_explain_case_1_teen_bonjour(self):
        """teen + 'bonjour' → fast, reason mentions 'teen'"""
        r = classify("teen", "bonjour")
        assert r.model_key == "fast"
        assert "teen" in r.reason.lower()

    def test_explain_case_2_dad_explique(self):
        """dad + 'explique' → full, reason mentions keyword"""
        r = classify("dad", "Explique-moi la différence entre RAM et ROM")
        assert r.model_key == "full"

    def test_explain_case_3_mom_merci(self):
        """mom + 'merci' → fast (conversational keyword)"""
        r = classify("mom", "merci beaucoup pour ton aide")
        assert r.model_key == "fast"
        assert "merci" in r.reason

    def test_explain_case_4_child_long_complex(self):
        """child + long complex message → fast (profile wins)"""
        msg = "Explique-moi les pros and cons des énergies renouvelables par rapport aux énergies fossiles dans le contexte actuel"
        r = classify("child", msg)
        assert r.model_key == "fast"
        assert "child" in r.reason.lower()

    def test_explain_case_5_dad_short_no_keyword(self):
        """dad + short message (< 15 words) + no keyword → fast (length rule)"""
        r = classify("dad", "Quelle est la capitale de la France ?")
        assert r.model_key == "fast"
        assert "threshold" in r.reason or "length" in r.reason or "conversational" in r.reason


class TestConflictResolution:
    """Conflict: profile vs message rules — profile wins."""

    def test_teen_complexity_keyword_still_fast(self):
        r = classify("teen", "Pourquoi le ciel est-il bleu ? Explique en détail.")
        assert r.model_key == "fast"

    def test_child_long_message_still_fast(self):
        long = " ".join(["mot"] * 40)
        r = classify("child", long)
        assert r.model_key == "fast"
