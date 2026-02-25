"""
Configuration management for Learning Sidecar using Pydantic models.
"""
import os
from typing import List
from pathlib import Path
import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Server configuration."""
    port: int = 10003


class LLMSidecarConfig(BaseModel):
    """LLM Sidecar connection configuration."""
    base_url: str = "http://localhost:10002"
    timeout_seconds: int = 30
    gate_user_id: str = "dad"


class ClaudeConfig(BaseModel):
    """Claude API configuration."""
    api_key_env: str = "ANTHROPIC_API_KEY"
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 256
    timeout_seconds: int = 15


class GatesConfig(BaseModel):
    """Gates validation configuration."""
    gate2a_confidence_threshold: float = 0.80
    personal_info_keywords: List[str] = Field(default_factory=list)


class StorageConfig(BaseModel):
    """Storage paths configuration."""
    base_path: str = "../../data/learning"


class NotificationConfig(BaseModel):
    """Desktop notification configuration."""
    enabled: bool = True
    command: str = "notify-send"


class Config(BaseModel):
    """Main configuration container."""
    server: ServerConfig
    llm_sidecar: LLMSidecarConfig
    claude: ClaudeConfig
    gates: GatesConfig
    storage: StorageConfig
    notification: NotificationConfig


def load_config(config_path: str = "config.yaml") -> Config:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Config object with all settings
    """
    config_file = Path(__file__).parent / config_path
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    with open(config_file, 'r') as f:
        config_data = yaml.safe_load(f)
    
    return Config(**config_data)


# Global config instance
config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global config
    if config is None:
        config = load_config()
    return config


def get_claude_api_key() -> str | None:
    """
    Get Claude API key from environment variable.
    
    Returns:
        API key if configured, None otherwise
    """
    cfg = get_config()
    return os.getenv(cfg.claude.api_key_env)
