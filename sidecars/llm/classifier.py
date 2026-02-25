"""
Heuristic query classifier for the LLM Sidecar.

Determines which Ollama model (fast/full) to use based on:
  - User profile (user_id)
  - Message length
  - Presence of conversational or complexity keywords

The classifier interface is designed to be easily swappable with an ML model
in the future: any replacement must implement the `classify` method with the
same signature and return a `ClassificationResult`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Protocol, runtime_checkable

from config import AppConfig, settings


# ---------------------------------------------------------------------------
# Keyword lists
# ---------------------------------------------------------------------------

def _keyword_match(keyword: str, text: str) -> bool:
    """
    Return True if `keyword` appears in `text` as a whole word / phrase.
    Uses regex word boundaries (\b) so that e.g. 'quoi' does NOT match 'pourquoi'.
    Multi-word phrases are matched literally between word boundaries.
    """
    # Escape the keyword for regex, then wrap in word boundaries
    pattern = r"\b" + re.escape(keyword) + r"\b"
    return bool(re.search(pattern, text, re.IGNORECASE | re.UNICODE))


FAST_KEYWORDS: List[str] = [
    "bonjour", "merci", "salut", "hello", "thanks", "ok",
    "oui", "non", "quoi", "c'est quoi", "c'est qui",
]

FULL_KEYWORDS: List[str] = [
    "explique", "analyse", "compare", "pourquoi", "comment fonctionne",
    "quelle est la différence", "pros and cons", "débat",
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    """Result returned by any classifier implementation."""
    model_key: str   # "fast" or "full"
    reason: str      # Human-readable explanation — useful for /classifier/explain


# ---------------------------------------------------------------------------
# Protocol (interface) — allows future ML-based replacement
# ---------------------------------------------------------------------------

@runtime_checkable
class QueryClassifier(Protocol):
    """Protocol that any classifier must satisfy."""

    def classify(self, user_id: str, message: str) -> ClassificationResult:
        ...


# ---------------------------------------------------------------------------
# Heuristic implementation
# ---------------------------------------------------------------------------

class HeuristicClassifier:
    """
    Rule-based classifier. Priority order:
    1. Profile has a forced model_preference → use it.
    2. Conversational keyword in message → fast.
    3. Complexity keyword in message → full.
    4. Message length < fast_threshold → fast.
    5. Message length > full_threshold → full.
    6. Default → fast.

    When profile forces a choice (teen/child → fast, or explicit preference),
    it overrides all other rules.
    """

    def __init__(self, config: AppConfig = settings) -> None:
        self._config = config

    def classify(self, user_id: str, message: str) -> ClassificationResult:
        profile = self._config.user_profiles.get(user_id)
        word_count = len(message.split())
        message_lower = message.lower()

        # --- Rule 1: profile-level forced preference -----------------------
        if profile is not None and profile.model_preference is not None:
            key = profile.model_preference  # "fast" or "full"
            return ClassificationResult(
                model_key=key,
                reason=f"user_profile={user_id} forces model_preference={key}",
            )

        # child / teen always fast (no model_preference set in yaml, but role=user)
        if user_id in ("child", "teen"):
            return ClassificationResult(
                model_key="fast",
                reason=f"user_profile={user_id} overrides all other rules → fast",
            )

        # --- Rule 2: conversational keyword → fast -------------------------
        for kw in FAST_KEYWORDS:
            if _keyword_match(kw, message_lower):
                return ClassificationResult(
                    model_key="fast",
                    reason=f"conversational keyword '{kw}' detected → fast",
                )

        # --- Rule 3: complexity keyword → full -----------------------------
        for kw in FULL_KEYWORDS:
            if _keyword_match(kw, message_lower):
                return ClassificationResult(
                    model_key="full",
                    reason=f"complexity keyword '{kw}' detected → full",
                )

        # --- Rule 4: short message → fast ----------------------------------
        fast_threshold = self._config.classifier.fast_threshold_words
        if word_count < fast_threshold:
            return ClassificationResult(
                model_key="fast",
                reason=f"message length ({word_count} words) < threshold ({fast_threshold}) → fast",
            )

        # --- Rule 5: long message → full -----------------------------------
        full_threshold = self._config.classifier.full_threshold_words
        if word_count > full_threshold:
            return ClassificationResult(
                model_key="full",
                reason=f"message length ({word_count} words) > threshold ({full_threshold}) → full",
            )

        # --- Default -------------------------------------------------------
        return ClassificationResult(
            model_key="fast",
            reason="no specific rule matched → default fast",
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_classifier(config: AppConfig = settings) -> QueryClassifier:
    """
    Return the appropriate classifier based on config.classifier.mode.
    Currently only 'heuristic' is implemented.
    """
    mode = config.classifier.mode
    if mode == "heuristic":
        return HeuristicClassifier(config)
    raise ValueError(f"Unknown classifier mode: '{mode}'. Supported: 'heuristic'")
