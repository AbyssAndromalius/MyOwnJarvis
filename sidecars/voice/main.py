"""
Voice Sidecar FastAPI application.
Handles voice processing pipeline via HTTP endpoints.
"""
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import numpy as np
import soundfile as sf
import io
import logging
from contextlib import asynccontextmanager

from config import get_config
from pipeline import VoicePipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global pipeline instance
pipeline: VoicePipeline = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Initializes pipeline on startup, cleanup on shutdown.
    """
    global pipeline
    
    # Startup
    logger.info("Starting Voice Sidecar...")
    try:
        config = get_config()
        pipeline = VoicePipeline(config)
        logger.info("Voice Sidecar started successfully")
    except Exception as e:
        logger.error(f"Failed to start Voice Sidecar: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Voice Sidecar...")


# Create FastAPI app
app = FastAPI(
    title="Voice Sidecar",
    description="Voice processing pipeline: VAD → Speaker ID → Transcription",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health():
    """
    Health check endpoint.
    
    Returns component statuses and loaded users.
    """
    if pipeline is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error": "Pipeline not initialized"
            }
        )
    
    health_status = pipeline.get_health()
    
    # Return 200 if healthy or degraded, 503 if error
    status_code = 200 if health_status["status"] in ["ok", "degraded"] else 503
    
    return JSONResponse(
        status_code=status_code,
        content=health_status
    )


@app.post("/voice/process")
async def process_voice(file: UploadFile = File(...)):
    """
    Process audio file through voice pipeline.
    
    Accepts WAV file via multipart/form-data.
    Returns identification, confidence, and transcript.
    """
    if pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="Pipeline not initialized"
        )
    
    # Validate file type
    if not file.filename.lower().endswith('.wav'):
        raise HTTPException(
            status_code=400,
            detail="Only WAV files are supported"
        )
    
    try:
        # Read uploaded file
        audio_bytes = await file.read()
        
        # Load audio using soundfile
        audio_data, sample_rate = sf.read(io.BytesIO(audio_bytes))
        
        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)
        
        # Ensure float32 format
        audio_data = audio_data.astype(np.float32)
        
        # Process through pipeline
        result = pipeline.process(audio_data, sample_rate)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Error processing audio: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Audio processing failed: {str(e)}"
        )


@app.post("/voice/reload-embeddings")
async def reload_embeddings():
    """
    Reload speaker embeddings from disk.
    
    Allows hot-reload after enrollment without restarting service.
    """
    if pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="Pipeline not initialized"
        )
    
    try:
        result = pipeline.reload_embeddings()
        
        if result.get("status") == "error":
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to reload embeddings")
            )
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reloading embeddings: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload embeddings: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler.
    Returns structured JSON error for all unhandled exceptions.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    # Get port from config
    config = get_config()
    port = config.server.port
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
