"""Unit tests for voice processing pipeline."""
import pytest, numpy as np
from unittest.mock import Mock, patch
from pathlib import Path

@pytest.fixture
def mock_config():
    config = Mock()
    config.server.port = 10001
    config.vad.threshold = 0.5
    config.vad.min_speech_duration_ms = 250
    config.vad.min_silence_duration_ms = 100
    config.speaker_id.embeddings_path = "/mock/embeddings"
    config.speaker_id.confidence_high = 0.75
    config.speaker_id.confidence_low = 0.60
    config.speaker_id.fallback_hierarchy = ["child","teen","mom","dad"]
    config.transcription.model = "base"
    config.transcription.device = "cuda"
    config.transcription.compute_type = "float16"
    config.transcription.language = None
    config.logging.access_log_path = "/tmp/access_log.jsonl"
    return config

@pytest.fixture  
def pipeline(mock_config, tmp_path):
    mock_config.logging.access_log_path = str(tmp_path / "access_log.jsonl")
    with patch('pipeline.SileroVAD') as mock_vad_cls, \
         patch('pipeline.SpeakerIdentifier') as mock_sid_cls, \
         patch('pipeline.Transcriber') as mock_trans_cls:
        mock_vad = Mock()
        mock_vad_cls.return_value = mock_vad
        mock_sid = Mock()
        mock_sid.get_status.return_value = ("ok", ["dad","mom","teen","child"])
        mock_sid_cls.return_value = mock_sid
        mock_trans = Mock()
        mock_trans_cls.return_value = mock_trans
        from pipeline import VoicePipeline
        p = VoicePipeline(mock_config)
        p._mock_vad, p._mock_sid, p._mock_trans = mock_vad, mock_sid, mock_trans
        return p

@pytest.fixture
def mock_audio():
    return np.random.randn(16000).astype(np.float32) * 0.1, 16000

class TestPipelineStates:
    def test_no_speech(self, pipeline, mock_audio):
        audio, sr = mock_audio
        pipeline._mock_vad.detect_speech.return_value = (False, 0.1)
        result = pipeline.process(audio, sr)
        assert result["status"] == "no_speech"
        assert result["user_id"] is None
        assert result["transcript"] is None

    def test_rejected(self, pipeline, mock_audio):
        audio, sr = mock_audio
        pipeline._mock_vad.detect_speech.return_value = (True, 0.8)
        pipeline._mock_sid.identify.return_value = (None, 0.45, False, None)
        result = pipeline.process(audio, sr)
        assert result["status"] == "rejected"
        assert result["confidence"] == 0.45
        assert result["transcript"] is None

    def test_identified(self, pipeline, mock_audio):
        audio, sr = mock_audio
        pipeline._mock_vad.detect_speech.return_value = (True, 0.9)
        pipeline._mock_sid.identify.return_value = ("dad", 0.87, False, None)
        pipeline._mock_trans.transcribe.return_value = ("Hello world", "en")
        result = pipeline.process(audio, sr)
        assert result["status"] == "identified"
        assert result["user_id"] == "dad"
        assert result["confidence"] == 0.87
        assert result["transcript"] == "Hello world"
        assert not result["fallback"]

    def test_fallback(self, pipeline, mock_audio):
        audio, sr = mock_audio
        pipeline._mock_vad.detect_speech.return_value = (True, 0.85)
        pipeline._mock_sid.identify.return_value = ("child", 0.68, True, "ambiguous_candidates: [dad, mom]")
        pipeline._mock_trans.transcribe.return_value = ("Can I play?", "en")
        result = pipeline.process(audio, sr)
        assert result["status"] == "fallback"
        assert result["user_id"] == "child"
        assert result["fallback"] is True
        assert result["transcript"] == "Can I play?"  # Transcription happens in fallback mode
