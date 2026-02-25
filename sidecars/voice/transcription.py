"""
Speech transcription using Faster Whisper.
Transcribes audio to text with language detection.
"""
import numpy as np
from typing import Tuple, Optional
import logging
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class Transcriber:
    """
    Wrapper for Faster Whisper model.
    Transcribes speech to text with automatic language detection.
    """
    
    def __init__(
        self,
        model_size: str = "base",
        device: str = "cuda",
        compute_type: str = "float16",
        language: Optional[str] = None
    ):
        """
        Initialize transcriber.
        
        Args:
            model_size: Whisper model size (base, small, medium, large)
            device: Device to run on ("cuda" or "cpu")
            compute_type: Compute type ("float16", "int8", "float32")
            language: Language code or None for auto-detection
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        
        try:
            # Initialize Faster Whisper model
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type
            )
            logger.info(f"Faster Whisper model '{model_size}' loaded on {device}")
            
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            
            # Try fallback to CPU if CUDA failed
            if device == "cuda":
                logger.warning("Falling back to CPU for Whisper")
                try:
                    self.device = "cpu"
                    self.compute_type = "int8"  # More efficient on CPU
                    self.model = WhisperModel(
                        model_size,
                        device="cpu",
                        compute_type="int8"
                    )
                    logger.info(f"Faster Whisper model '{model_size}' loaded on CPU")
                except Exception as cpu_error:
                    logger.error(f"Failed to load Whisper model on CPU: {cpu_error}")
                    raise
            else:
                raise
    
    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> Tuple[str, str]:
        """
        Transcribe audio to text.
        
        Args:
            audio_data: Audio numpy array (mono, float32)
            sample_rate: Sample rate in Hz
            
        Returns:
            Tuple of (transcript, language_code)
        """
        try:
            # Faster Whisper expects audio as numpy array
            # Resample to 16kHz if needed
            if sample_rate != 16000:
                audio_data = self._resample(audio_data, sample_rate, 16000)
            
            # Transcribe
            segments, info = self.model.transcribe(
                audio_data,
                language=self.language,
                beam_size=5,
                vad_filter=False  # We already did VAD
            )
            
            # Collect all segments into full transcript
            transcript_parts = []
            for segment in segments:
                transcript_parts.append(segment.text)
            
            transcript = " ".join(transcript_parts).strip()
            detected_language = info.language
            
            return transcript, detected_language
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return "", "unknown"
    
    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """
        Resample audio to target sample rate.
        
        Args:
            audio: Audio numpy array
            orig_sr: Original sample rate
            target_sr: Target sample rate
            
        Returns:
            Resampled audio numpy array
        """
        try:
            import librosa
            resampled = librosa.resample(
                audio,
                orig_sr=orig_sr,
                target_sr=target_sr
            )
            return resampled
        except Exception as e:
            logger.warning(f"Resampling failed: {e}, returning original audio")
            return audio
    
    def get_status(self) -> str:
        """
        Get transcription system status.
        
        Returns:
            Status string: "ok" or "error"
        """
        try:
            # Simple check - if model exists, we're ok
            if hasattr(self, 'model') and self.model is not None:
                return "ok"
            return "error"
        except:
            return "error"
