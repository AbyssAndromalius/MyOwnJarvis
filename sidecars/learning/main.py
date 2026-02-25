"""
Learning Sidecar FastAPI Application
Manages supervised learning corrections with 3-gate validation pipeline.
"""
import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx

from config import get_config, get_claude_api_key
from storage import Storage
from notifier import Notifier
from pipeline import Pipeline
from gates.gate3_admin import apply_to_memory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
storage: Storage | None = None
notifier: Notifier | None = None
pipeline: Pipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources."""
    global storage, notifier, pipeline
    
    logger.info("Starting Learning Sidecar...")
    
    # Initialize components
    storage = Storage()
    notifier = Notifier()
    pipeline = Pipeline(storage, notifier)
    
    logger.info("Learning Sidecar started successfully")
    
    yield
    
    logger.info("Shutting down Learning Sidecar...")


app = FastAPI(
    title="Learning Sidecar",
    description="Supervised learning corrections with 3-gate validation",
    version="1.0.0",
    lifespan=lifespan
)


# Request/Response Models
class SubmitCorrectionRequest(BaseModel):
    """Request model for submitting a correction."""
    user_id: str
    content: str
    source: str = "user_correction"


class SubmitCorrectionResponse(BaseModel):
    """Response model for correction submission."""
    id: str
    status: str


class ReviewCorrectionRequest(BaseModel):
    """Request model for reviewing a correction."""
    action: str  # approve or reject
    caller_id: str
    reason: str | None = None


class ReviewCorrectionResponse(BaseModel):
    """Response model for correction review."""
    id: str
    status: str
    memory_id: str | None = None
    reason: str | None = None


class PendingCorrectionItem(BaseModel):
    """Item in pending corrections list."""
    id: str
    user_id: str
    content: str
    submitted_at: str


class PendingCorrectionsResponse(BaseModel):
    """Response model for pending corrections list."""
    count: int
    items: List[PendingCorrectionItem]


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    llm_sidecar: str
    claude_api: str
    pending_count: int
    storage: str


# Endpoints
@app.post("/learning/submit", response_model=SubmitCorrectionResponse)
async def submit_correction(
    request: SubmitCorrectionRequest,
    background_tasks: BackgroundTasks
):
    """
    Submit a correction for validation.
    
    Starts the 3-gate pipeline asynchronously and returns immediately.
    """
    logger.info(f"Received correction from user {request.user_id}")
    
    # Create correction
    correction = storage.create_correction(
        user_id=request.user_id,
        content=request.content,
        source=request.source
    )
    
    # Save initial state
    storage.save_correction(correction)
    
    # Process in background
    background_tasks.add_task(pipeline.process_correction, correction)
    
    return SubmitCorrectionResponse(
        id=correction.id,
        status="processing"
    )


@app.get("/learning/status/{correction_id}")
async def get_correction_status(correction_id: str):
    """Get the current status of a correction."""
    correction = storage.load_correction(correction_id)
    
    if not correction:
        raise HTTPException(status_code=404, detail="Correction not found")
    
    return correction.model_dump()


@app.get("/learning/pending", response_model=PendingCorrectionsResponse)
async def get_pending_corrections():
    """Get all corrections pending admin approval (Gate 3)."""
    corrections = storage.list_pending()
    
    items = [
        PendingCorrectionItem(
            id=c.id,
            user_id=c.user_id,
            content=c.content,
            submitted_at=c.submitted_at
        )
        for c in corrections
    ]
    
    return PendingCorrectionsResponse(
        count=len(items),
        items=items
    )


@app.post("/learning/review/{correction_id}", response_model=ReviewCorrectionResponse)
async def review_correction(correction_id: str, request: ReviewCorrectionRequest):
    """
    Review a correction (approve or reject).
    
    Only callable by admin users (dad or mom).
    """
    # Verify caller is authorized
    if request.caller_id not in ["dad", "mom"]:
        raise HTTPException(status_code=403, detail="Unauthorized: only dad or mom can review")
    
    # Load correction
    correction = storage.load_correction(correction_id)
    if not correction:
        raise HTTPException(status_code=404, detail="Correction not found")
    
    # Verify correction is pending Gate 3
    if correction.final_status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Correction not pending review (status: {correction.final_status})"
        )
    
    # Validate action
    if request.action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")
    
    # For reject, reason is required
    if request.action == "reject" and not request.reason:
        raise HTTPException(status_code=400, detail="Reason required for rejection")
    
    logger.info(f"Reviewing correction {correction_id}: {request.action} by {request.caller_id}")
    
    # Update Gate 3 status
    storage.update_gate3_review(
        correction,
        action=request.action,
        reviewer=request.caller_id,
        reason=request.reason
    )
    
    # If approved, apply to memory
    memory_id = None
    if request.action == "approve":
        memory_id = await apply_to_memory(correction)
        if memory_id:
            storage.mark_applied(correction, memory_id)
            logger.info(f"Correction {correction_id} applied to memory: {memory_id}")
        else:
            logger.error(f"Failed to apply correction {correction_id} to memory")
            # Reload to get updated status
            correction = storage.load_correction(correction_id)
    
    return ReviewCorrectionResponse(
        id=correction.id,
        status=correction.final_status,
        memory_id=memory_id,
        reason=request.reason
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health and dependencies."""
    config = get_config()
    
    # Check LLM Sidecar
    llm_status = "unreachable"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{config.llm_sidecar.base_url}/health")
            if response.status_code == 200:
                llm_status = "reachable"
    except Exception:
        pass
    
    # Check Claude API configuration
    claude_status = "configured" if get_claude_api_key() else "not_configured"
    
    # Check storage
    storage_status = "ok" if storage.health_check() else "error"
    
    # Get pending count
    pending_count = storage.get_pending_count()
    
    return HealthResponse(
        status="ok",
        llm_sidecar=llm_status,
        claude_api=claude_status,
        pending_count=pending_count,
        storage=storage_status
    )


if __name__ == "__main__":
    import uvicorn
    config = get_config()
    uvicorn.run(app, host="0.0.0.0", port=config.server.port)
