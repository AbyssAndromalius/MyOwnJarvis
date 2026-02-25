"""
Inference pipeline for the LLM Sidecar.

Orchestrates:
  1. Query classification → model selection
  2. Vector memory retrieval (user + shared)
  3. Prompt construction (system prompt + memories + history + user message)
  4. Ollama API call
  5. Response packaging
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from classifier import ClassificationResult, HeuristicClassifier, get_classifier
from config import AppConfig, settings as app_settings
from memory import ChromaMemory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response types (plain dicts — FastAPI handles serialization)
# ---------------------------------------------------------------------------

class InferenceResult:
    """Structured result from the inference pipeline."""

    def __init__(
        self,
        response: str,
        model_used: str,
        memories_used: List[str],
        user_id: str,
    ) -> None:
        self.response = response
        self.model_used = model_used
        self.memories_used = memories_used
        self.user_id = user_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response": self.response,
            "model_used": self.model_used,
            "memories_used": self.memories_used,
            "user_id": self.user_id,
        }


# ---------------------------------------------------------------------------
# Inference engine
# ---------------------------------------------------------------------------

class InferenceEngine:
    """
    Main inference engine.

    Keeps a single httpx.AsyncClient for all Ollama calls.
    Can be used as an async context manager.
    """

    def __init__(
        self,
        config: AppConfig = app_settings,
        memory: Optional[ChromaMemory] = None,
    ) -> None:
        self._config = config
        self._classifier = get_classifier(config)
        self._memory = memory or ChromaMemory(config)
        self._http_client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialize the async HTTP client."""
        self._http_client = httpx.AsyncClient(
            base_url=self._config.ollama.base_url,
            timeout=self._config.ollama.timeout_seconds,
        )

    async def stop(self) -> None:
        """Close the async HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self) -> "InferenceEngine":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(
        self,
        user_id: str,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> InferenceResult:
        """
        Full pipeline:
        classify → retrieve memories → build prompt → call Ollama → return result.
        """
        if self._http_client is None:
            raise RuntimeError("InferenceEngine not started. Call await engine.start() first.")

        # 1. Classify
        classification: ClassificationResult = self._classifier.classify(user_id, message)
        model_name = self._resolve_model(classification.model_key)

        # 2. Retrieve memories
        memories = self._memory.search(user_id=user_id, query=message, top_k=5)
        memory_texts = [m["content"] for m in memories]

        # 3. Build prompt
        messages = self._build_messages(
            user_id=user_id,
            user_message=message,
            memories=memory_texts,
            history=conversation_history or [],
        )

        # 4. Call Ollama
        response_text = await self._call_ollama(model=model_name, messages=messages)

        return InferenceResult(
            response=response_text,
            model_used=model_name,
            memories_used=memory_texts,
            user_id=user_id,
        )

    async def check_ollama_health(self) -> Dict[str, Any]:
        """Check Ollama availability and list available models."""
        if self._http_client is None:
            return {"status": "error", "detail": "HTTP client not initialized"}
        try:
            resp = await self._http_client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            available = [m["name"] for m in data.get("models", [])]
            return {"status": "reachable", "models_available": available}
        except Exception as exc:
            return {"status": "unreachable", "detail": str(exc)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_model(self, model_key: str) -> str:
        """Convert 'fast'/'full' key to the actual model name from config."""
        models = self._config.ollama.models
        if model_key == "fast":
            return models.fast
        if model_key == "full":
            return models.full
        raise ValueError(f"Unknown model key: '{model_key}'")

    def _build_messages(
        self,
        user_id: str,
        user_message: str,
        memories: List[str],
        history: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """
        Assemble the messages list for Ollama chat API:
          [system, ...history, user_message_with_memory_context]
        """
        profile = self._config.user_profiles.get(user_id)
        system_prompt = profile.system_prompt if profile else "You are a helpful assistant."

        # Inject memories into system prompt if any
        if memories:
            memory_block = "\n".join(f"- {m}" for m in memories)
            system_prompt = (
                f"{system_prompt}\n\n"
                f"Relevant context from memory:\n{memory_block}"
            )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        # Append conversation history
        for turn in history:
            if turn.get("role") in ("user", "assistant"):
                messages.append({"role": turn["role"], "content": turn["content"]})

        # Append current user message
        messages.append({"role": "user", "content": user_message})
        return messages

    async def _call_ollama(
        self,
        model: str,
        messages: List[Dict[str, str]],
    ) -> str:
        """
        Call the Ollama /api/chat endpoint (non-streaming).
        Returns the assistant message content.
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        try:
            resp = await self._http_client.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
        except httpx.HTTPStatusError as exc:
            logger.error("Ollama HTTP error: %s", exc)
            raise RuntimeError(f"Ollama returned {exc.response.status_code}: {exc.response.text}") from exc
        except Exception as exc:
            logger.error("Ollama call failed: %s", exc)
            raise RuntimeError(f"Ollama call failed: {exc}") from exc
