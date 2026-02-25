"""
Unit tests for the ChromaMemory wrapper.
Uses an in-memory ChromaDB client (no persistence, no Ollama required).

Run with: pytest tests/test_memory.py -v
"""
from __future__ import annotations

import sys
import os
import time
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock
from config import load_config, AppConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tmp_config() -> AppConfig:
    """Config pointing to a temporary directory for ChromaDB."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = load_config()
        # Override chromadb path to temp dir
        cfg.chromadb.path = tmpdir
        yield cfg


@pytest.fixture(scope="module")
def mem(tmp_config):
    """Fresh ChromaMemory instance backed by temp storage."""
    from memory import ChromaMemory
    return ChromaMemory(tmp_config)


# ---------------------------------------------------------------------------
# Test: add and retrieve
# ---------------------------------------------------------------------------

class TestMemoryAddAndSearch:

    def test_add_returns_uuid(self, mem):
        """add() should return a non-empty string ID."""
        entry_id = mem.add("dad", "Dad loves Python programming", source="conversation")
        assert isinstance(entry_id, str)
        assert len(entry_id) > 0

    def test_search_finds_added_memory(self, mem):
        """A recently added memory should appear in search results."""
        mem.add("dad", "Dad prefers code examples in Python", source="approved_learning")
        results = mem.search("dad", "Python code examples", top_k=5)
        contents = [r["content"] for r in results]
        assert any("Python" in c for c in contents)

    def test_search_returns_score(self, mem):
        """Search results should have a score between 0 and 1."""
        mem.add("mom", "Mom likes concise explanations", source="conversation")
        results = mem.search("mom", "concise", top_k=3)
        for r in results:
            assert 0.0 <= r["score"] <= 1.0

    def test_search_includes_metadata(self, mem):
        """Search results should include source and timestamp fields."""
        mem.add("teen", "Teen enjoys gaming", source="conversation")
        results = mem.search("teen", "gaming", top_k=3)
        assert len(results) > 0
        first = results[0]
        assert "source" in first
        assert "timestamp" in first
        assert first["timestamp"] != ""


# ---------------------------------------------------------------------------
# Test: user isolation
# ---------------------------------------------------------------------------

class TestCollectionIsolation:

    def test_dad_memory_not_visible_to_teen(self, mem):
        """A memory added for dad should NOT appear in teen's search results."""
        secret = "dad_secret_unique_memory_xyzzy_42"
        mem.add("dad", secret, source="conversation")

        teen_results = mem.search("teen", secret, top_k=5)
        teen_contents = [r["content"] for r in teen_results]
        assert not any(secret in c for c in teen_contents), (
            "dad's private memory leaked into teen's results"
        )

    def test_mom_memory_not_visible_to_child(self, mem):
        """A memory added for mom should NOT appear in child's results."""
        secret = "mom_private_note_abc123"
        mem.add("mom", secret, source="approved_learning")

        child_results = mem.search("child", secret, top_k=5)
        child_contents = [r["content"] for r in child_results]
        assert not any(secret in c for c in child_contents)

    def test_dad_memory_visible_to_dad_only(self, mem):
        """A memory added for dad should appear in dad's results."""
        unique = "dad_exclusive_memory_789xyz"
        mem.add("dad", unique, source="conversation")

        dad_results = mem.search("dad", unique, top_k=5)
        dad_contents = [r["content"] for r in dad_results]
        assert any(unique in c for c in dad_contents)


# ---------------------------------------------------------------------------
# Test: shared collection
# ---------------------------------------------------------------------------

class TestSharedCollection:

    def test_shared_memory_visible_to_all_users(self, mem):
        """A shared memory entry should be found by all user queries."""
        shared_content = "shared_fact_visible_to_all_users_abc"
        mem.add("shared", shared_content, source="approved_learning")

        for uid in ("dad", "mom", "teen", "child"):
            results = mem.search(uid, shared_content, top_k=5)
            contents = [r["content"] for r in results]
            assert any(shared_content in c for c in contents), (
                f"Shared memory not visible to user '{uid}'"
            )


# ---------------------------------------------------------------------------
# Test: delete
# ---------------------------------------------------------------------------

class TestMemoryDelete:

    def test_delete_removes_entry(self, mem):
        """Deleting an entry should make it no longer findable."""
        unique = "entry_to_be_deleted_zzzyx"
        entry_id = mem.add("dad", unique, source="conversation")

        deleted = mem.delete("dad", entry_id)
        assert deleted is True

        # Entry should no longer appear in search
        results = mem.search("dad", unique, top_k=5)
        contents = [r["content"] for r in results]
        assert not any(unique in c for c in contents)

    def test_delete_nonexistent_returns_false(self, mem):
        """Deleting an unknown ID should return False without raising."""
        result = mem.delete("dad", "non-existent-id-00000")
        assert result is False


# ---------------------------------------------------------------------------
# Test: validation
# ---------------------------------------------------------------------------

class TestValidation:

    def test_add_invalid_user_raises(self, mem):
        with pytest.raises(ValueError, match="Unknown user_id"):
            mem.add("unknown_user", "some content")

    def test_search_invalid_user_raises(self, mem):
        with pytest.raises(ValueError, match="Unknown user_id"):
            mem.search("ghost", "query")


# ---------------------------------------------------------------------------
# Test: health check
# ---------------------------------------------------------------------------

class TestHealthCheck:

    def test_is_healthy_returns_true(self, mem):
        assert mem.is_healthy() is True
