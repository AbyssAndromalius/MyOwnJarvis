"""
Configuration loader for Voice Sidecar.
Loads and validates config.yaml using Pydantic models.
"""
from pathlib import Path
from typing import Optional, List
import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Server configuration."""
    port: int = 10001


class VADConfig(BaseModel):
    """Voice Activity Detection configuration."""
    model: str = "silero_vad"
    threshold: float = 0.5
    min_speech_duration_ms: int = 250
    min_silence_duration_ms: int = 100


class SpeakerIDConfig(BaseModel):
    """Speaker identification configuration."""
    confidence_high: float = 0.75
    confidence_low: float = 0.60
    embeddings_path: str = "../../data/voice/embeddings"
    fallback_hierarchy: List[str] = Field(default_factory=lambda: ["child", "teen", "mom", "dad"])


class TranscriptionConfig(BaseModel):
    """Transcription configuration."""
    model: str = "base"  # base | small | medium
    device: str = "cuda"
    compute_type: str = "float16"
    language: Optional[str] = None  # null = auto-detect


class LoggingConfig(BaseModel):
    """Logging configuration."""
    access_log_path: str = "../../data/voice/access_logs/access_log.jsonl"


class Config(BaseModel):
    """Root configuration model."""
    server: ServerConfig
    vad: VADConfig
    speaker_id: SpeakerIDConfig
    transcription: TranscriptionConfig
    logging: LoggingConfig


def load_config(config_path: str = "config.yaml") -> Config:
    """
    Load and validate configuration from YAML file.
    
    Args:
        config_path: Path to config.yaml file
        
    Returns:
        Validated Config object
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        config_dict = yaml.safe_load(f)
    
    return Config(**config_dict)


# Global config instance - loaded once at startup
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get the global configuration instance.
    Loads config on first call.
    
    Returns:
        Global Config object
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> Config:
    """
    Force reload configuration from disk.
    
    Returns:
        Newly loaded Config object
    """
    global _config
    _config = load_config()
    return _config
