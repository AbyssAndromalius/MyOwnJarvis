"""
ChromaDB wrapper for the LLM Sidecar.

Each user has an isolated collection: memory_<user_id>.
A shared read-only collection `memory_shared` is accessible by all users.

Embeddings are generated locally with sentence-transformers (all-MiniLM-L6-v2).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

# Allow injecting a mock embedder in tests via environment variable
_MOCK_EMBEDDINGS = os.environ.get("LLM_SIDECAR_MOCK_EMBEDDINGS", "0") == "1"

if not _MOCK_EMBEDDINGS:
    from sentence_transformers import SentenceTransformer

from config import AppConfig, settings as app_settings


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHARED_COLLECTION = "memory_shared"
VALID_USER_IDS = {"dad", "mom", "teen", "child"}


# ---------------------------------------------------------------------------
# Memory entry schema (typed dict for clarity)
# ---------------------------------------------------------------------------

class MemoryEntry(dict):
    """Typed convenience wrapper — not enforced at runtime, just for IDE hints."""
    content: str
    user_id: str
    timestamp: str
    source: str
    metadata: Dict[str, Any]


# ---------------------------------------------------------------------------
# ChromaMemory
# ---------------------------------------------------------------------------

class ChromaMemory:
    """
    Manages per-user ChromaDB collections with sentence-transformer embeddings.

    Collections:
        memory_dad, memory_mom, memory_teen, memory_child — private per user
        memory_shared — general approved facts, readable by all
    """

    def __init__(self, config: AppConfig = app_settings) -> None:
        self._config = config
        self._client = chromadb.PersistentClient(
            path=config.chromadb.path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        if _MOCK_EMBEDDINGS:
            # Lightweight deterministic embedder for unit tests (no torch required)
            import hashlib
            import math

            class _MockEmbedder:
                def encode(self, text: str, **kwargs) -> list:
                    """Hash-based pseudo-embedding of fixed dimension 384."""
                    dim = 384
                    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
                    rng = __import__("random").Random(seed)
                    vec = [rng.gauss(0, 1) for _ in range(dim)]
                    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
                    return [x / norm for x in vec]

            self._embedder = _MockEmbedder()
        else:
            self._embedder = SentenceTransformer(config.embeddings.model)
        # Pre-create all known collections so they always exist
        self._ensure_collections()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collection_name(self, user_id: str) -> str:
        """Map a user_id to its collection name."""
        return f"memory_{user_id}"

    def _ensure_collections(self) -> None:
        """Create collections for all known users + shared if missing."""
        for uid in VALID_USER_IDS:
            self._client.get_or_create_collection(self._collection_name(uid))
        self._client.get_or_create_collection(SHARED_COLLECTION)

    def _embed(self, text: str) -> List[float]:
        """Generate a single embedding vector."""
        result = self._embedder.encode(text, normalize_embeddings=True)
        # SentenceTransformer returns numpy array; mock returns list
        return result.tolist() if hasattr(result, "tolist") else list(result)

    def _get_collection(self, name: str):
        """Retrieve an existing ChromaDB collection by name."""
        return self._client.get_collection(name)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(
        self,
        user_id: str,
        content: str,
        source: str = "conversation",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add a memory entry to the user's private collection.
        Returns the generated UUID for the entry.
        """
        if user_id not in VALID_USER_IDS and user_id != "shared":
            raise ValueError(f"Unknown user_id: '{user_id}'")

        entry_id = str(uuid.uuid4())
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        doc_metadata = {
            "user_id": user_id,
            "timestamp": timestamp,
            "source": source,
            **(metadata or {}),
        }

        collection_name = (
            SHARED_COLLECTION if user_id == "shared"
            else self._collection_name(user_id)
        )
        collection = self._get_collection(collection_name)
        embedding = self._embed(content)

        collection.add(
            ids=[entry_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[doc_metadata],
        )
        return entry_id

    def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search the user's private collection + memory_shared.
        Returns a merged, deduplicated list sorted by relevance score (desc).
        """
        if user_id not in VALID_USER_IDS:
            raise ValueError(f"Unknown user_id: '{user_id}'")

        query_embedding = self._embed(query)
        results: List[Dict[str, Any]] = []

        # Search user-specific collection
        user_col = self._get_collection(self._collection_name(user_id))
        user_count = user_col.count()
        if user_count > 0:
            user_res = user_col.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, user_count),
                include=["documents", "metadatas", "distances"],
            )
            results.extend(self._format_results(user_res))

        # Search shared collection
        shared_col = self._get_collection(SHARED_COLLECTION)
        shared_count = shared_col.count()
        if shared_count > 0:
            shared_res = shared_col.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, shared_count),
                include=["documents", "metadatas", "distances"],
            )
            results.extend(self._format_results(shared_res))

        # Sort by score descending and cap at top_k
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    def delete(self, user_id: str, memory_id: str) -> bool:
        """
        Delete a memory entry by ID from the user's collection.
        Also checks shared collection.
        Returns True if deleted, False if not found.
        """
        collections_to_check = [
            self._collection_name(user_id),
            SHARED_COLLECTION,
        ]
        for col_name in collections_to_check:
            try:
                col = self._get_collection(col_name)
                existing = col.get(ids=[memory_id])
                if existing["ids"]:
                    col.delete(ids=[memory_id])
                    return True
            except Exception:
                continue
        return False

    def is_healthy(self) -> bool:
        """Return True if ChromaDB client is responsive."""
        try:
            self._client.heartbeat()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _format_results(query_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert raw ChromaDB query results to a flat list of dicts."""
        formatted = []
        ids = query_result.get("ids", [[]])[0]
        documents = query_result.get("documents", [[]])[0]
        metadatas = query_result.get("metadatas", [[]])[0]
        distances = query_result.get("distances", [[]])[0]

        for i, doc_id in enumerate(ids):
            # ChromaDB distance is L2 or cosine distance; convert to similarity score
            distance = distances[i] if i < len(distances) else 1.0
            # For normalized cosine embeddings: similarity = 1 - distance/2
            score = max(0.0, 1.0 - distance / 2.0)
            meta = metadatas[i] if i < len(metadatas) else {}
            formatted.append({
                "id": doc_id,
                "content": documents[i] if i < len(documents) else "",
                "score": round(score, 4),
                "source": meta.get("source", "unknown"),
                "timestamp": meta.get("timestamp", ""),
                "user_id": meta.get("user_id", ""),
            })
        return formatted
