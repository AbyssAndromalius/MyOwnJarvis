"""
Speaker identification using Resemblyzer.
Compares voice embeddings to identify known users.
"""
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import logging
from resemblyzer import VoiceEncoder, preprocess_wav

logger = logging.getLogger(__name__)


class SpeakerIdentifier:
    """
    Speaker identification using Resemblyzer embeddings.
    Implements confidence-based decision logic with fallback hierarchy.
    """
    
    def __init__(
        self,
        embeddings_path: str,
        confidence_high: float = 0.75,
        confidence_low: float = 0.60,
        fallback_hierarchy: List[str] = None
    ):
        """
        Initialize speaker identifier.
        
        Args:
            embeddings_path: Path to directory containing user embeddings (.npy files)
            confidence_high: Threshold for normal identification (≥ 0.75)
            confidence_low: Threshold for fallback mode (≥ 0.60)
            fallback_hierarchy: Order of restriction (most to least restrictive)
        """
        self.embeddings_path = Path(embeddings_path)
        self.confidence_high = confidence_high
        self.confidence_low = confidence_low
        self.fallback_hierarchy = fallback_hierarchy or ["child", "teen", "mom", "dad"]
        
        # User embeddings storage
        self.user_embeddings: Dict[str, np.ndarray] = {}
        
        # Initialize voice encoder
        try:
            self.encoder = VoiceEncoder()
            logger.info("Resemblyzer VoiceEncoder loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load VoiceEncoder: {e}")
            raise
        
        # Load embeddings
        self.load_embeddings()
    
    def load_embeddings(self) -> Dict[str, List[str]]:
        """
        Load user embeddings from disk.
        
        Returns:
            Dict with 'loaded' and 'missing' user lists
        """
        loaded = []
        missing = []
        
        # Create embeddings directory if it doesn't exist
        self.embeddings_path.mkdir(parents=True, exist_ok=True)
        
        # Expected users from fallback hierarchy
        expected_users = set(self.fallback_hierarchy)
        
        for user in expected_users:
            embedding_file = self.embeddings_path / f"{user}.npy"
            
            if embedding_file.exists():
                try:
                    embedding = np.load(embedding_file)
                    
                    # Validate embedding shape
                    if embedding.shape != (256,):
                        logger.warning(
                            f"Invalid embedding shape for {user}: {embedding.shape}, expected (256,)"
                        )
                        missing.append(user)
                        continue
                    
                    self.user_embeddings[user] = embedding
                    loaded.append(user)
                    logger.info(f"Loaded embedding for user: {user}")
                    
                except Exception as e:
                    logger.warning(f"Failed to load embedding for {user}: {e}")
                    missing.append(user)
            else:
                logger.warning(f"Embedding file not found for user: {user}")
                missing.append(user)
        
        if not loaded:
            logger.warning("No user embeddings loaded - speaker identification will be degraded")
        
        return {"loaded": loaded, "missing": missing}
    
    def reload_embeddings(self) -> Dict[str, List[str]]:
        """
        Reload embeddings from disk without restarting.
        
        Returns:
            Dict with 'loaded' and 'missing' user lists
        """
        logger.info("Reloading user embeddings...")
        self.user_embeddings.clear()
        return self.load_embeddings()
    
    def identify(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> Tuple[Optional[str], float, bool, Optional[str]]:
        """
        Identify speaker from audio.
        
        Args:
            audio_data: Audio numpy array (mono, float32)
            sample_rate: Sample rate in Hz
            
        Returns:
            Tuple of (user_id, confidence, is_fallback, fallback_reason)
            - user_id: Identified user or None if rejected
            - confidence: Similarity score (0.0 - 1.0)
            - is_fallback: True if using fallback hierarchy
            - fallback_reason: Explanation for fallback or None
        """
        if not self.user_embeddings:
            logger.warning("No user embeddings loaded - cannot identify speaker")
            return None, 0.0, False, None
        
        try:
            # Preprocess audio for Resemblyzer (expects 16kHz)
            preprocessed = preprocess_wav(audio_data, source_sr=sample_rate)
            
            # Generate embedding
            embedding = self.encoder.embed_utterance(preprocessed)
            
            # Compute similarities with all known users
            similarities = {}
            for user, user_embedding in self.user_embeddings.items():
                similarity = self._cosine_similarity(embedding, user_embedding)
                similarities[user] = similarity
            
            # Find best match
            best_user = max(similarities, key=similarities.get)
            best_score = similarities[best_user]
            
            # Apply decision logic
            return self._apply_decision_logic(similarities, best_user, best_score)
            
        except Exception as e:
            logger.error(f"Speaker identification failed: {e}")
            return None, 0.0, False, None
    
    def _cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (0.0 - 1.0)
        """
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        
        # Clamp to [0, 1] range
        return float(max(0.0, min(1.0, similarity)))
    
    def _apply_decision_logic(
        self,
        similarities: Dict[str, float],
        best_user: str,
        best_score: float
    ) -> Tuple[Optional[str], float, bool, Optional[str]]:
        """
        Apply 3-tier confidence decision logic.
        
        Args:
            similarities: Dict of user -> similarity scores
            best_user: User with highest similarity
            best_score: Highest similarity score
            
        Returns:
            Tuple of (user_id, confidence, is_fallback, fallback_reason)
        """
        # Tier 1: High confidence - normal identification
        if best_score >= self.confidence_high:
            return best_user, best_score, False, None
        
        # Tier 3: Low confidence - reject
        if best_score < self.confidence_low:
            return None, best_score, False, None
        
        # Tier 2: Medium confidence (0.60-0.74) - fallback to most restrictive profile
        # Find all candidates with score >= 0.60 (candidates proches)
        candidates = [
            user for user, score in similarities.items()
            if score >= self.confidence_low
        ]
        
        if len(candidates) == 1:
            # Single candidate in fallback range - use that candidate
            fallback_user = candidates[0]
            fallback_reason = f"single_candidate: {fallback_user}"
        else:
            # Multiple candidates - use most restrictive AMONG these candidates
            fallback_user = self._get_most_restrictive(candidates)
            fallback_reason = f"ambiguous_candidates: {sorted(candidates)}"
        
        return fallback_user, best_score, True, fallback_reason
    
    def _get_most_restrictive(self, candidates: List[str]) -> str:
        """
        Get most restrictive profile from candidates based on hierarchy.
        
        Args:
            candidates: List of candidate user IDs
            
        Returns:
            Most restrictive user ID from candidates
        """
        # Fallback hierarchy is ordered from most to least restrictive
        # Return the first one that appears in candidates
        for user in self.fallback_hierarchy:
            if user in candidates:
                return user
        
        # Fallback: return first candidate if none match hierarchy
        return candidates[0]
    
    def get_status(self) -> Tuple[str, List[str]]:
        """
        Get current status of speaker identification system.
        
        Returns:
            Tuple of (status, loaded_users)
            - status: "ok", "degraded", or "error"
            - loaded_users: List of users with loaded embeddings
        """
        loaded_users = list(self.user_embeddings.keys())
        
        if not loaded_users:
            return "error", []
        
        expected_users = set(self.fallback_hierarchy)
        missing_users = expected_users - set(loaded_users)
        
        if missing_users:
            return "degraded", loaded_users
        
        return "ok", loaded_users
