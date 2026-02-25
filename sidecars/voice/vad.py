"""
Voice Activity Detection using Silero VAD.
Filters out silent audio files before expensive processing.
"""
import torch
import numpy as np
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class SileroVAD:
    """
    Wrapper for Silero VAD model.
    Detects voice activity in audio to filter out silence.
    """
    
    def __init__(
        self,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 100
    ):
        """
        Initialize Silero VAD.
        
        Args:
            threshold: Speech probability threshold (0.0 - 1.0)
            min_speech_duration_ms: Minimum duration of speech to detect
            min_silence_duration_ms: Minimum duration of silence between speech
        """
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        
        try:
            # Load Silero VAD from torch hub
            self.model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            
            # Extract utility functions
            (self.get_speech_timestamps,
             self.save_audio,
             self.read_audio,
             self.VADIterator,
             self.collect_chunks) = utils
            
            logger.info("Silero VAD loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load Silero VAD: {e}")
            raise
    
    def detect_speech(self, audio_data: np.ndarray, sample_rate: int) -> Tuple[bool, float]:
        """
        Detect if audio contains speech.
        
        Args:
            audio_data: Audio numpy array (mono, float32)
            sample_rate: Sample rate in Hz
            
        Returns:
            Tuple of (has_speech: bool, speech_probability: float)
        """
        try:
            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio_data).float()
            
            # Resample to 16kHz if needed (Silero VAD expects 16kHz)
            if sample_rate != 16000:
                audio_tensor = self._resample(audio_tensor, sample_rate, 16000)
            
            # Get speech timestamps
            speech_timestamps = self.get_speech_timestamps(
                audio_tensor,
                self.model,
                threshold=self.threshold,
                min_speech_duration_ms=self.min_speech_duration_ms,
                min_silence_duration_ms=self.min_silence_duration_ms,
                return_seconds=False
            )
            
            # Calculate speech probability (percentage of audio with speech)
            if len(speech_timestamps) > 0:
                total_speech_samples = sum(
                    chunk['end'] - chunk['start'] 
                    for chunk in speech_timestamps
                )
                speech_prob = total_speech_samples / len(audio_tensor)
                has_speech = True
            else:
                speech_prob = 0.0
                has_speech = False
            
            return has_speech, speech_prob
            
        except Exception as e:
            logger.error(f"VAD detection failed: {e}")
            # On error, assume speech is present to avoid false negatives
            return True, 1.0
    
    def _resample(self, audio: torch.Tensor, orig_sr: int, target_sr: int) -> torch.Tensor:
        """
        Resample audio to target sample rate.
        
        Args:
            audio: Audio tensor
            orig_sr: Original sample rate
            target_sr: Target sample rate
            
        Returns:
            Resampled audio tensor
        """
        import torchaudio
        resampler = torchaudio.transforms.Resample(orig_sr, target_sr)
        return resampler(audio)
