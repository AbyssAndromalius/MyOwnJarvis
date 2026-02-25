"""
Voice processing pipeline orchestrator.
Coordinates VAD → Speaker ID → Transcription workflow.
"""
import numpy as np
from typing import Dict, Any, Optional
import logging
from pathlib import Path

from vad import SileroVAD
from speaker_id import SpeakerIdentifier
from transcription import Transcriber
from access_logger import AccessLogger
from config import Config

logger = logging.getLogger(__name__)


class VoicePipeline:
    """
    Orchestrates the complete voice processing pipeline:
    1. VAD - Filter silent audio
    2. Speaker ID - Identify user
    3. Transcription - Convert speech to text
    """
    
    def __init__(self, config: Config):
        """
        Initialize voice pipeline.
        
        Args:
            config: Configuration object
        """
        self.config = config
        
        # Initialize components
        logger.info("Initializing voice pipeline components...")
        
        # VAD
        try:
            self.vad = SileroVAD(
                threshold=config.vad.threshold,
                min_speech_duration_ms=config.vad.min_speech_duration_ms,
                min_silence_duration_ms=config.vad.min_silence_duration_ms
            )
            self.vad_status = "ok"
        except Exception as e:
            logger.error(f"VAD initialization failed: {e}")
            self.vad = None
            self.vad_status = "error"
        
        # Speaker ID
        try:
            self.speaker_id = SpeakerIdentifier(
                embeddings_path=config.speaker_id.embeddings_path,
                confidence_high=config.speaker_id.confidence_high,
                confidence_low=config.speaker_id.confidence_low,
                fallback_hierarchy=config.speaker_id.fallback_hierarchy
            )
            self.speaker_id_status, self.loaded_users = self.speaker_id.get_status()
        except Exception as e:
            logger.error(f"Speaker ID initialization failed: {e}")
            self.speaker_id = None
            self.speaker_id_status = "error"
            self.loaded_users = []
        
        # Transcription
        try:
            self.transcriber = Transcriber(
                model_size=config.transcription.model,
                device=config.transcription.device,
                compute_type=config.transcription.compute_type,
                language=config.transcription.language
            )
            self.transcription_status = "ok"
        except Exception as e:
            logger.error(f"Transcription initialization failed: {e}")
            self.transcriber = None
            self.transcription_status = "error"
        
        # Access logger
        self.access_logger = AccessLogger(config.logging.access_log_path)
        
        logger.info("Voice pipeline initialization complete")
    
    def process(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> Dict[str, Any]:
        """
        Process audio through complete pipeline.
        
        Args:
            audio_data: Audio numpy array (mono, float32)
            sample_rate: Sample rate in Hz
            
        Returns:
            Dict with processing results:
            {
                "status": "identified" | "fallback" | "rejected" | "no_speech",
                "user_id": str | None,
                "confidence": float | None,
                "transcript": str | None,
                "language": str | None,
                "audio_duration_seconds": float,
                "fallback": bool,
                "fallback_reason": str | None
            }
        """
        # Calculate audio duration
        audio_duration = len(audio_data) / sample_rate
        
        # Step 1: Voice Activity Detection
        if self.vad is None:
            logger.warning("VAD not available, skipping VAD check")
            has_speech = True
        else:
            has_speech, speech_prob = self.vad.detect_speech(audio_data, sample_rate)
            
            if not has_speech:
                logger.info(f"No speech detected (prob: {speech_prob:.2f})")
                result = {
                    "status": "no_speech",
                    "user_id": None,
                    "confidence": None,
                    "transcript": None,
                    "language": None,
                    "audio_duration_seconds": round(audio_duration, 2),
                    "fallback": False,
                    "fallback_reason": None
                }
                
                # Log to access log
                self.access_logger.log_identification(
                    event="no_speech",
                    user_id=None,
                    confidence=None,
                    audio_duration_seconds=audio_duration
                )
                
                return result
        
        # Step 2: Speaker Identification
        if self.speaker_id is None:
            logger.error("Speaker ID not available, cannot process audio")
            return self._error_result(audio_duration, "Speaker identification unavailable")
        
        user_id, confidence, is_fallback, fallback_reason = self.speaker_id.identify(
            audio_data,
            sample_rate
        )
        
        # Check if speaker was rejected (confidence < 0.60)
        if user_id is None:
            logger.info(f"Speaker rejected (confidence: {confidence:.2f})")
            result = {
                "status": "rejected",
                "user_id": None,
                "confidence": round(confidence, 2),
                "transcript": None,
                "language": None,
                "audio_duration_seconds": round(audio_duration, 2),
                "fallback": False,
                "fallback_reason": None
            }
            
            # Log to access log
            self.access_logger.log_identification(
                event="rejected",
                user_id=None,
                confidence=confidence,
                audio_duration_seconds=audio_duration
            )
            
            return result
        
        # Step 3: Transcription (only if speaker identified with confidence >= 0.60)
        if self.transcriber is None:
            logger.error("Transcriber not available, cannot transcribe")
            transcript = ""
            language = "unknown"
        else:
            transcript, language = self.transcriber.transcribe(audio_data, sample_rate)
        
        # Determine status
        if is_fallback:
            status = "fallback"
            event = "fallback"
        else:
            status = "identified"
            event = "identified"
        
        logger.info(
            f"Speaker {status}: {user_id} (confidence: {confidence:.2f}), "
            f"transcript: '{transcript[:50]}...'"
        )
        
        result = {
            "status": status,
            "user_id": user_id,
            "confidence": round(confidence, 2),
            "transcript": transcript,
            "language": language,
            "audio_duration_seconds": round(audio_duration, 2),
            "fallback": is_fallback,
            "fallback_reason": fallback_reason
        }
        
        # Log to access log
        self.access_logger.log_identification(
            event=event,
            user_id=user_id,
            confidence=confidence,
            audio_duration_seconds=audio_duration,
            fallback_reason=fallback_reason
        )
        
        return result
    
    def _error_result(self, audio_duration: float, error_msg: str) -> Dict[str, Any]:
        """
        Create error result.
        
        Args:
            audio_duration: Duration of audio
            error_msg: Error message
            
        Returns:
            Error result dict
        """
        return {
            "status": "error",
            "user_id": None,
            "confidence": None,
            "transcript": None,
            "language": None,
            "audio_duration_seconds": round(audio_duration, 2),
            "fallback": False,
            "fallback_reason": None,
            "error": error_msg
        }
    
    def reload_embeddings(self) -> Dict[str, Any]:
        """
        Reload speaker embeddings from disk.
        
        Returns:
            Dict with reload status and user lists
        """
        if self.speaker_id is None:
            return {
                "status": "error",
                "error": "Speaker identification not initialized"
            }
        
        result = self.speaker_id.reload_embeddings()
        
        # Update cached status
        self.speaker_id_status, self.loaded_users = self.speaker_id.get_status()
        
        return {
            "status": "reloaded",
            "loaded_users": result["loaded"],
            "missing_users": result["missing"]
        }
    
    def get_health(self) -> Dict[str, Any]:
        """
        Get health status of all pipeline components.
        
        Returns:
            Dict with component statuses
        """
        return {
            "status": "ok" if self._is_healthy() else "degraded",
            "vad": self.vad_status,
            "speaker_id": self.speaker_id_status,
            "transcription": self.transcription_status,
            "loaded_users": self.loaded_users,
            "whisper_model": self.config.transcription.model
        }
    
    def _is_healthy(self) -> bool:
        """
        Check if pipeline is healthy.
        
        Returns:
            True if all critical components are ok
        """
        # VAD can be degraded, but speaker_id and transcription must be ok
        return (
            self.speaker_id_status in ["ok", "degraded"] and
            self.transcription_status == "ok"
        )
