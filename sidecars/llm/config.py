"""
Configuration loading and Pydantic models for the LLM Sidecar.
Reads config.yaml and exposes typed configuration objects.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ServerConfig(BaseModel):
    port: int = 10002


class OllamaModels(BaseModel):
    fast: str = "llama3.2:3b-instruct-q4_0"
    full: str = "llama3.1:8b-instruct-q4_0"


class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    models: OllamaModels = Field(default_factory=OllamaModels)
    timeout_seconds: int = 60


class ChromaDBConfig(BaseModel):
    path: str = "../../data/memory"


class EmbeddingsConfig(BaseModel):
    model: str = "all-MiniLM-L6-v2"


class ClassifierConfig(BaseModel):
    mode: str = "heuristic"
    fast_threshold_words: int = 15
    full_threshold_words: int = 30


class MemoryConfig(BaseModel):
    chat_top_k: int = 5  # memories injected into the prompt per /chat request


class UserProfileConfig(BaseModel):
    role: str  # "admin" or "user"
    model_preference: Optional[str] = None  # "fast" | "full" | null
    system_prompt: str


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    chromadb: ChromaDBConfig = Field(default_factory=ChromaDBConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    classifier: ClassifierConfig = Field(default_factory=ClassifierConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    user_profiles: Dict[str, UserProfileConfig] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(path: Optional[str] = None) -> AppConfig:
    """
    Load configuration from a YAML file.
    Defaults to config.yaml in the same directory as this file.
    """
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "config.yaml")

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path.resolve()}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return AppConfig(**raw)


# Singleton — loaded once at import time
settings: AppConfig = load_config()
