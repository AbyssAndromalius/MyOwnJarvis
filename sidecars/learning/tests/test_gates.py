"""
Tests for individual gates with mocked external dependencies.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from gates.gate1_sanity import validate_gate1
from gates.gate2a_local_factcheck import validate_gate2a, is_personal_info
from gates.gate2b_claude import validate_gate2b


@pytest.mark.asyncio
async def test_gate1_pass():
    """Test Gate 1 passing a valid correction."""
    with patch('httpx.AsyncClient') as mock_client:
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": '{"verdict": "pass", "reason": "Coherent and safe"}'
        }
        mock_response.raise_for_status = MagicMock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        
        status, reason = await validate_gate1("La réunion est à 9h")
        
        assert status == "pass"
        assert "Coherent" in reason


@pytest.mark.asyncio
async def test_gate1_reject():
    """Test Gate 1 rejecting harmful content."""
    with patch('httpx.AsyncClient') as mock_client:
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": '{"verdict": "reject", "reason": "Contains harmful content"}'
        }
        mock_response.raise_for_status = MagicMock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        
        status, reason = await validate_gate1("harmful content")
        
        assert status == "reject"
        assert "harmful" in reason.lower()


@pytest.mark.asyncio
async def test_gate1_llm_timeout():
    """Test Gate 1 handling LLM timeout."""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        
        status, reason = await validate_gate1("Some content")
        
        assert status == "error"
        assert "timeout" in reason.lower()


@pytest.mark.asyncio
async def test_gate1_invalid_json():
    """Test Gate 1 handling invalid JSON from LLM."""
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "This is not valid JSON"
        }
        mock_response.raise_for_status = MagicMock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        
        status, reason = await validate_gate1("Some content")
        
        assert status == "error"
        assert "parsing error" in reason.lower()


@pytest.mark.asyncio
async def test_gate2a_personal_info_detection():
    """Test Gate 2a detecting and auto-passing personal information."""
    # Test various personal info keywords
    test_cases = [
        "Ma fille s'appelle Alice",
        "Son prénom est Bob",
        "Elle habite à Paris",
        "Notre famille est grande",
        "Mon anniversaire est le 15 mars"
    ]
    
    for content in test_cases:
        status, confidence, reason, is_personal = await validate_gate2a(content)
        
        assert is_personal is True
        assert status == "pass"
        assert confidence == 1.0
        assert "Personal information" in reason


def test_is_personal_info():
    """Test personal info keyword detection."""
    assert is_personal_info("Elle s'appelle Marie") is True
    assert is_personal_info("Son prénom est Jean") is True
    assert is_personal_info("Il habite à Lyon") is True
    assert is_personal_info("Notre chien est mignon") is True
    assert is_personal_info("Normal statement") is False


@pytest.mark.asyncio
async def test_gate2a_high_confidence_pass():
    """Test Gate 2a passing with high confidence."""
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": '{"verdict": "pass", "confidence": 0.92, "reason": "Factually plausible"}'
        }
        mock_response.raise_for_status = MagicMock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        
        status, confidence, reason, is_personal = await validate_gate2a("The sky is blue")
        
        assert status == "pass"
        assert confidence == 0.92
        assert is_personal is False


@pytest.mark.asyncio
async def test_gate2a_low_confidence():
    """Test Gate 2a returning low confidence."""
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": '{"verdict": "pass", "confidence": 0.60, "reason": "Uncertain"}'
        }
        mock_response.raise_for_status = MagicMock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        
        status, confidence, reason, is_personal = await validate_gate2a("Some uncertain fact")
        
        assert status == "pass"
        assert confidence == 0.60
        assert confidence < 0.80  # Below threshold


@pytest.mark.asyncio
async def test_gate2b_pass():
    """Test Gate 2b passing with Claude API."""
    with patch('anthropic.AsyncAnthropic') as mock_anthropic:
        # Mock Claude response
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"verdict": "pass", "reason": "Factually accurate"}')]
        
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client
        
        with patch('config.get_claude_api_key', return_value="test-key"):
            status, reason = await validate_gate2b("The Earth orbits the Sun")
            
            assert status == "pass"
            assert "accurate" in reason.lower()


@pytest.mark.asyncio
async def test_gate2b_reject():
    """Test Gate 2b rejecting incorrect information."""
    with patch('anthropic.AsyncAnthropic') as mock_anthropic:
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"verdict": "reject", "reason": "Factually incorrect"}')]
        
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client
        
        with patch('config.get_claude_api_key', return_value="test-key"):
            status, reason = await validate_gate2b("The Sun orbits the Earth")
            
            assert status == "reject"
            assert "incorrect" in reason.lower()


@pytest.mark.asyncio
async def test_gate2b_no_api_key():
    """Test Gate 2b handling missing API key."""
    with patch('config.get_claude_api_key', return_value=None):
        status, reason = await validate_gate2b("Some fact")
        
        assert status == "pass"
        assert "gate2b_unavailable" in reason


@pytest.mark.asyncio
async def test_gate2b_api_error():
    """Test Gate 2b handling API errors."""
    with patch('anthropic.AsyncAnthropic') as mock_anthropic:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API Error"))
        mock_anthropic.return_value = mock_client
        
        with patch('config.get_claude_api_key', return_value="test-key"):
            status, reason = await validate_gate2b("Some fact")
            
            # Should auto-pass on error (don't block indefinitely)
            assert status == "pass"
            assert "gate2b_unavailable" in reason


@pytest.mark.asyncio
async def test_gate1_json_with_backticks():
    """Test Gate 1 parsing JSON wrapped in markdown code blocks."""
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": '```json\n{"verdict": "pass", "reason": "OK"}\n```'
        }
        mock_response.raise_for_status = MagicMock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        
        status, reason = await validate_gate1("Content")
        
        assert status == "pass"
        assert reason == "OK"
