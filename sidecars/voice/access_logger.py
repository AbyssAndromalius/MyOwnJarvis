"""
Security access logger for Voice Sidecar.
Logs all identification attempts to JSONL format.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class AccessLogger:
    """
    Logs speaker identification attempts to JSONL file.
    Each line is a complete JSON object.
    """
    
    def __init__(self, log_path: str):
        """
        Initialize access logger.
        
        Args:
            log_path: Path to JSONL log file
        """
        self.log_path = Path(log_path)
        
        # Create parent directories if they don't exist
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create log file if it doesn't exist
        if not self.log_path.exists():
            self.log_path.touch()
    
    def log_identification(
        self,
        event: str,
        user_id: Optional[str],
        confidence: Optional[float],
        audio_duration_seconds: float,
        fallback_reason: Optional[str] = None
    ):
        """
        Log an identification event.
        
        Args:
            event: Event type - "identified", "fallback", "rejected", or "no_speech"
            user_id: Identified user ID or None
            confidence: Confidence score or None
            audio_duration_seconds: Duration of audio file
            fallback_reason: Reason for fallback (e.g., "ambiguous_candidates: [dad, mom]")
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": event,
            "user_id": user_id,
            "confidence": confidence,
            "fallback_reason": fallback_reason,
            "audio_duration_seconds": round(audio_duration_seconds, 2)
        }
        
        try:
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to write access log: {e}")
