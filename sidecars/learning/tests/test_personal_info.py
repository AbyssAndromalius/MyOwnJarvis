"""
Tests for personal information detection.
"""
import pytest
from gates.gate2a_local_factcheck import is_personal_info


def test_personal_info_detection_sappelle():
    """Test detection with 's'appelle' keyword."""
    assert is_personal_info("Elle s'appelle Marie") is True
    assert is_personal_info("Il s'appelle Jean") is True
    assert is_personal_info("Ma fille s'appelle Alice") is True


def test_personal_info_detection_prenom():
    """Test detection with 'prénom' keyword."""
    assert is_personal_info("Son prénom est Bob") is True
    assert is_personal_info("Le prénom de ma mère est Anne") is True


def test_personal_info_detection_habite():
    """Test detection with 'habite' keyword."""
    assert is_personal_info("Elle habite à Paris") is True
    assert is_personal_info("Il habite rue de la Paix") is True
    assert is_personal_info("Ma famille habite en France") is True


def test_personal_info_detection_adresse():
    """Test detection with 'adresse' keyword."""
    assert is_personal_info("Mon adresse est 123 rue Example") is True
    assert is_personal_info("L'adresse de la maison") is True


def test_personal_info_detection_anniversaire():
    """Test detection with 'anniversaire' keyword."""
    assert is_personal_info("Son anniversaire est le 15 mars") is True
    assert is_personal_info("Mon anniversaire est en juin") is True


def test_personal_info_detection_ne_le():
    """Test detection with 'né le' keyword."""
    assert is_personal_info("Il est né le 10 avril 1990") is True
    assert is_personal_info("Elle est née le 5 mai") is True


def test_personal_info_detection_travaille_chez():
    """Test detection with 'travaille chez' keyword."""
    assert is_personal_info("Il travaille chez Google") is True
    assert is_personal_info("Elle travaille chez Microsoft") is True


def test_personal_info_detection_numero():
    """Test detection with 'son numéro' keyword."""
    assert is_personal_info("Son numéro de téléphone est...") is True
    assert is_personal_info("Voici son numéro") is True


def test_personal_info_detection_notre():
    """Test detection with 'notre' keyword."""
    assert is_personal_info("Notre maison est grande") is True
    assert is_personal_info("Notre famille est nombreuse") is True


def test_personal_info_detection_ma_famille():
    """Test detection with 'ma famille' keyword."""
    assert is_personal_info("Ma famille aime voyager") is True
    assert is_personal_info("Dans ma famille, on est quatre") is True


def test_no_personal_info_detection():
    """Test that normal statements are not detected as personal info."""
    test_cases = [
        "La réunion est à 9h",
        "Le ciel est bleu",
        "Paris est la capitale de la France",
        "Il fait beau aujourd'hui",
        "Le chat dort sur le canapé",
        "La voiture est rouge",
        "Le livre est intéressant"
    ]
    
    for content in test_cases:
        assert is_personal_info(content) is False, f"False positive for: {content}"


def test_case_insensitive_detection():
    """Test that detection is case-insensitive."""
    assert is_personal_info("Elle S'APPELLE Marie") is True
    assert is_personal_info("NOTRE maison") is True
    assert is_personal_info("Son PRÉNOM est Bob") is True


def test_partial_word_match():
    """Test that keywords match as substrings."""
    # These should match because keywords are substrings
    assert is_personal_info("Quelqu'un s'appelle Jean") is True
    
    # But this shouldn't cause false positives
    assert is_personal_info("J'appelle mon ami") is False  # "appelle" not "s'appelle"


def test_multiple_keywords():
    """Test detection with multiple personal info keywords."""
    content = "Ma fille s'appelle Alice et elle habite à Lyon"
    assert is_personal_info(content) is True


def test_edge_cases():
    """Test edge cases for personal info detection."""
    # Empty string
    assert is_personal_info("") is False
    
    # Only keyword
    assert is_personal_info("s'appelle") is True
    
    # Keyword at beginning
    assert is_personal_info("Notre maison") is True
    
    # Keyword at end
    assert is_personal_info("C'est notre") is True


def test_french_accents():
    """Test that French accents are handled correctly."""
    assert is_personal_info("Son prénom est Marc") is True
    assert is_personal_info("Il est né") is True


@pytest.mark.asyncio
async def test_personal_info_bypass_integration():
    """Test that personal info corrections bypass Gate 2b in integration."""
    from gates.gate2a_local_factcheck import validate_gate2a
    from unittest.mock import patch, AsyncMock
    
    # Personal info should auto-pass without calling LLM
    with patch('httpx.AsyncClient') as mock_client:
        # This should NOT be called for personal info
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=Exception("Should not be called for personal info")
        )
        
        status, confidence, reason, is_personal = await validate_gate2a(
            "Ma fille s'appelle Alice"
        )
        
        # Should pass without calling LLM
        assert status == "pass"
        assert confidence == 1.0
        assert is_personal is True
        assert "Personal information" in reason
        
        # Verify LLM was NOT called
        mock_client.return_value.__aenter__.return_value.post.assert_not_called()
