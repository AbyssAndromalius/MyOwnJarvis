"""
Integration tests for the inference pipeline.
⚠ These tests require Ollama to be running on http://localhost:11434.

Run with: pytest tests/test_inference.py -v
Skip gracefully if Ollama is unavailable: pytest tests/test_inference.py -v -k "not requires_ollama"
"""
from __future__ import annotations

import sys
import os
import asyncio
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pytest_asyncio
import httpx

from config import load_config
from inference import InferenceEngine
from memory import ChromaMemory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ollama_is_running() -> bool:
    """Quick sync check to see if Ollama is reachable."""
    try:
        with httpx.Client(timeout=3) as client:
            resp = client.get("http://localhost:11434/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


skip_if_no_ollama = pytest.mark.skipif(
    not ollama_is_running(),
    reason="Ollama not running — skipping integration tests",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tmp_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = load_config()
        cfg.chromadb.path = tmpdir
        yield cfg


@pytest.fixture(scope="module")
def mem(tmp_config):
    return ChromaMemory(tmp_config)


@pytest_asyncio.fixture(scope="module")
async def eng(tmp_config, mem):
    engine = InferenceEngine(config=tmp_config, memory=mem)
    await engine.start()
    yield engine
    await engine.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@skip_if_no_ollama
@pytest.mark.asyncio
async def test_health_ollama_reachable(eng):
    """Health check should report Ollama as reachable."""
    info = await eng.check_ollama_health()
    assert info["status"] == "reachable"
    assert "models_available" in info


@skip_if_no_ollama
@pytest.mark.asyncio
async def test_chat_dad_uses_full_model_for_complex_query(eng):
    """
    A complex message from dad should use the full model.
    'Explique' triggers the complexity keyword rule.
    """
    result = await eng.chat(
        user_id="dad",
        message="Explique-moi la différence entre TCP et UDP en détail.",
    )
    assert result.model_used == eng._config.ollama.models.full
    assert len(result.response) > 0
    assert result.user_id == "dad"


@skip_if_no_ollama
@pytest.mark.asyncio
async def test_chat_teen_uses_fast_model(eng):
    """Teen profile always uses the fast model."""
    result = await eng.chat(
        user_id="teen",
        message="Salut ! Comment tu vas ?",
    )
    assert result.model_used == eng._config.ollama.models.fast
    assert len(result.response) > 0


@skip_if_no_ollama
@pytest.mark.asyncio
async def test_chat_child_uses_fast_model(eng):
    """Child profile always uses the fast model."""
    result = await eng.chat(
        user_id="child",
        message="Raconte-moi une histoire drôle",
    )
    assert result.model_used == eng._config.ollama.models.fast


@skip_if_no_ollama
@pytest.mark.asyncio
async def test_chat_with_memory_context(eng, mem):
    """Memories added before a query should appear in the response context."""
    mem.add(
        user_id="dad",
        content="Dad prefers Python code examples with type hints",
        source="approved_learning",
    )
    result = await eng.chat(
        user_id="dad",
        message="Give me a short code snippet",
    )
    assert result.memories_used is not None
    # At least one memory should have been retrieved
    assert len(result.memories_used) > 0


@skip_if_no_ollama
@pytest.mark.asyncio
async def test_chat_with_conversation_history(eng):
    """Conversation history should be passed to Ollama without error."""
    history = [
        {"role": "user", "content": "Bonjour !"},
        {"role": "assistant", "content": "Bonjour ! Comment puis-je vous aider ?"},
    ]
    result = await eng.chat(
        user_id="mom",
        message="Merci, j'avais une question sur les vitamines",
        conversation_history=history,
    )
    assert len(result.response) > 0


@skip_if_no_ollama
@pytest.mark.asyncio
async def test_chat_returns_model_name_string(eng):
    """model_used must be a non-empty string (the actual model name)."""
    result = await eng.chat(user_id="teen", message="ok")
    assert isinstance(result.model_used, str)
    assert result.model_used in (
        eng._config.ollama.models.fast,
        eng._config.ollama.models.full,
    )
