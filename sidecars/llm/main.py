"""
LLM Sidecar — FastAPI application entry point.

Exposes:
  POST /chat
  POST /memory/add
  POST /memory/search
  DELETE /memory/{user_id}/{memory_id}
  GET  /health
  GET  /classifier/explain

Runs on port 10002 (configurable via config.yaml).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from classifier import get_classifier
from config import settings
from inference import InferenceEngine
from memory import ChromaMemory, VALID_USER_IDS

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("llm_sidecar")

# ---------------------------------------------------------------------------
# Shared singletons (initialized in lifespan)
# ---------------------------------------------------------------------------

memory_store: ChromaMemory = None          # type: ignore[assignment]
engine: InferenceEngine = None             # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated startup/shutdown events)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown shared resources."""
    global memory_store, engine

    logger.info("Initializing ChromaDB memory store...")
    memory_store = ChromaMemory(settings)

    logger.info("Initializing inference engine...")
    engine = InferenceEngine(config=settings, memory=memory_store)
    await engine.start()

    logger.info("LLM Sidecar ready on port %d", settings.server.port)
    yield

    logger.info("Shutting down inference engine...")
    await engine.stop()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="LLM Sidecar",
    description="Local LLM inference and vector memory service",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

class ConversationTurn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    user_id: str
    message: str
    conversation_history: Optional[List[ConversationTurn]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str
    model_used: str
    memories_used: List[str]
    user_id: str


class MemoryAddRequest(BaseModel):
    user_id: str
    content: str
    source: str = "conversation"
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class MemoryAddResponse(BaseModel):
    id: str
    status: str


class MemorySearchRequest(BaseModel):
    user_id: str
    query: str
    top_k: int = 5


class MemorySearchResult(BaseModel):
    content: str
    score: float
    source: str
    timestamp: str


class MemorySearchResponse(BaseModel):
    results: List[MemorySearchResult]


class DeleteMemoryBody(BaseModel):
    caller_id: str


class ClassifierExplainResponse(BaseModel):
    model_selected: str
    reason: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Run the full inference pipeline for a user message.
    Selects the appropriate model, retrieves relevant memories,
    builds the prompt, and calls Ollama.
    """
    if request.user_id not in VALID_USER_IDS:
        raise HTTPException(status_code=400, detail=f"Unknown user_id: '{request.user_id}'")

    history = [t.model_dump() for t in (request.conversation_history or [])]

    try:
        result = await engine.chat(
            user_id=request.user_id,
            message=request.message,
            conversation_history=history,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"error": "Inference failed", "detail": str(exc)}) from exc

    return ChatResponse(**result.to_dict())


@app.post("/memory/add", response_model=MemoryAddResponse)
async def memory_add(request: MemoryAddRequest) -> MemoryAddResponse:
    """Add a memory entry to a user's collection."""
    if request.user_id not in VALID_USER_IDS:
        raise HTTPException(status_code=400, detail=f"Unknown user_id: '{request.user_id}'")

    try:
        entry_id = memory_store.add(
            user_id=request.user_id,
            content=request.content,
            source=request.source,
            metadata=request.metadata or {},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return MemoryAddResponse(id=entry_id, status="added")


@app.post("/memory/search", response_model=MemorySearchResponse)
async def memory_search(request: MemorySearchRequest) -> MemorySearchResponse:
    """Search a user's memory collection (includes shared memories)."""
    if request.user_id not in VALID_USER_IDS:
        raise HTTPException(status_code=400, detail=f"Unknown user_id: '{request.user_id}'")

    try:
        raw_results = memory_store.search(
            user_id=request.user_id,
            query=request.query,
            top_k=request.top_k,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    results = [
        MemorySearchResult(
            content=r["content"],
            score=r["score"],
            source=r["source"],
            timestamp=r["timestamp"],
        )
        for r in raw_results
    ]
    return MemorySearchResponse(results=results)


@app.delete("/memory/{user_id}/{memory_id}")
async def memory_delete(
    user_id: str,
    memory_id: str,
    body: DeleteMemoryBody,
) -> Dict[str, Any]:
    """
    Delete a memory entry.
    Restricted to admin users (dad or mom) — caller_id must be in the request body.
    """
    # Validate caller is an admin
    caller_profile = settings.user_profiles.get(body.caller_id)
    if caller_profile is None or caller_profile.role != "admin":
        raise HTTPException(
            status_code=403,
            detail=f"caller_id '{body.caller_id}' is not authorized to delete memories.",
        )

    if user_id not in VALID_USER_IDS:
        raise HTTPException(status_code=400, detail=f"Unknown user_id: '{user_id}'")

    deleted = memory_store.delete(user_id=user_id, memory_id=memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found.")

    return {"status": "deleted", "memory_id": memory_id}


@app.get("/health")
async def health() -> Dict[str, Any]:
    """
    Health check endpoint.
    Reports Ollama reachability and ChromaDB status.
    Starts cleanly even if Ollama is temporarily unavailable.
    """
    ollama_info = await engine.check_ollama_health()

    chroma_ok = memory_store.is_healthy()

    configured_models = [
        settings.ollama.models.fast,
        settings.ollama.models.full,
    ]

    return {
        "status": "ok",
        "ollama": ollama_info.get("status", "unknown"),
        "chromadb": "ok" if chroma_ok else "error",
        "models_available": ollama_info.get("models_available", configured_models),
    }


@app.get("/classifier/explain", response_model=ClassifierExplainResponse)
async def classifier_explain(
    user_id: str = Query(..., description="User profile ID"),
    message: str = Query(..., description="The message to classify"),
) -> ClassifierExplainResponse:
    """
    Debug endpoint: show which model would be selected for a given user/message
    and the reason for that decision.
    """
    classifier = get_classifier(settings)
    result = classifier.classify(user_id=user_id, message=message)
    model_name = (
        settings.ollama.models.fast
        if result.model_key == "fast"
        else settings.ollama.models.full
    )
    return ClassifierExplainResponse(
        model_selected=model_name,
        reason=result.reason,
    )
