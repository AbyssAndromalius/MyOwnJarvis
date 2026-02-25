"""Unit tests for speaker identification decision logic."""
import pytest, numpy as np
from unittest.mock import Mock, patch

@pytest.fixture
def mock_embeddings(tmp_path):
    embeddings_dir = tmp_path / "embeddings"
    embeddings_dir.mkdir()
    for user in ["dad","mom","teen","child"]:
        embedding = np.random.randn(256).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        np.save(embeddings_dir / f"{user}.npy", embedding)
    return str(embeddings_dir)

@pytest.fixture
def speaker_id(mock_embeddings):
    with patch('speaker_id.VoiceEncoder') as mock_encoder:
        mock_encoder.return_value = Mock()
        from speaker_id import SpeakerIdentifier
        return SpeakerIdentifier(mock_embeddings, 0.75, 0.60, ["child","teen","mom","dad"])

class TestDecisionLogic:
    def test_high_confidence(self, speaker_id):
        sims = {"dad": 0.87, "mom": 0.45, "teen": 0.32, "child": 0.28}
        user_id, conf, fallback, reason = speaker_id._apply_decision_logic(sims, "dad", 0.87)
        assert user_id == "dad" and conf == 0.87 and not fallback and reason is None

    def test_low_confidence_rejection(self, speaker_id):
        sims = {"dad": 0.52, "mom": 0.48, "teen": 0.45, "child": 0.41}
        user_id, conf, fallback, reason = speaker_id._apply_decision_logic(sims, "dad", 0.52)
        assert user_id is None and conf == 0.52 and not fallback

    def test_single_candidate_fallback(self, speaker_id):
        sims = {"dad": 0.55, "mom": 0.67, "teen": 0.52, "child": 0.48}
        user_id, conf, fallback, reason = speaker_id._apply_decision_logic(sims, "mom", 0.67)
        assert user_id == "mom" and fallback and "single_candidate" in reason

    def test_multiple_candidates_most_restrictive(self, speaker_id):
        # dad=0.72, mom=0.63 both >= 0.60 → should return mom (most restrictive among candidates)
        sims = {"dad": 0.72, "mom": 0.63, "teen": 0.55, "child": 0.50}
        user_id, conf, fallback, reason = speaker_id._apply_decision_logic(sims, "dad", 0.72)
        assert user_id == "mom" and fallback and "ambiguous" in reason

    def test_fallback_with_all_candidates(self, speaker_id):
        # All >= 0.60 → should return child (most restrictive)
        sims = {"dad": 0.72, "mom": 0.68, "teen": 0.65, "child": 0.63}
        user_id, conf, fallback, reason = speaker_id._apply_decision_logic(sims, "dad", 0.72)
        assert user_id == "child" and fallback

    def test_boundary_075(self, speaker_id):
        sims = {"dad": 0.75, "mom": 0.40}
        user_id, conf, fallback, reason = speaker_id._apply_decision_logic(sims, "dad", 0.75)
        assert user_id == "dad" and not fallback  # Exactly 0.75 → normal

    def test_boundary_060(self, speaker_id):
        sims = {"dad": 0.60, "mom": 0.40}
        user_id, conf, fallback, reason = speaker_id._apply_decision_logic(sims, "dad", 0.60)
        assert user_id == "dad" and fallback  # Exactly 0.60 → fallback

    def test_below_060(self, speaker_id):
        sims = {"dad": 0.5999, "mom": 0.40}
        user_id, conf, fallback, reason = speaker_id._apply_decision_logic(sims, "dad", 0.5999)
        assert user_id is None  # Below 0.60 → rejected
