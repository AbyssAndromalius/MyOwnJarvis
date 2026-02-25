"""
Tests for the complete learning pipeline.
All external dependencies (LLM Sidecar, Claude API) are mocked.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from storage import Storage, Correction
from notifier import Notifier
from pipeline import Pipeline


@pytest.fixture
def storage(tmp_path):
    """Create a storage instance with temporary directory."""
    storage = Storage(base_path=str(tmp_path / "learning"))
    return storage


@pytest.fixture
def notifier():
    """Create a notifier instance."""
    return Notifier()


@pytest.fixture
def pipeline_instance(storage, notifier):
    """Create a pipeline instance."""
    return Pipeline(storage, notifier)


@pytest.mark.asyncio
async def test_pipeline_full_pass(pipeline_instance, storage):
    """Test correction passing through all gates successfully."""
    correction = storage.create_correction(
        user_id="mom",
        content="La réunion du lundi est à 9h"
    )
    
    # Mock Gate 1 - pass
    with patch('gates.gate1_sanity.validate_gate1', new_callable=AsyncMock) as mock_gate1:
        mock_gate1.return_value = ("pass", "Coherent and safe")
        
        # Mock Gate 2a - pass with high confidence
        with patch('gates.gate2a_local_factcheck.validate_gate2a', new_callable=AsyncMock) as mock_gate2a:
            mock_gate2a.return_value = ("pass", 0.92, "Factually plausible", False)
            
            # Mock notification
            with patch.object(pipeline_instance.notifier, 'notify_learning_review'):
                await pipeline_instance.process_correction(correction)
    
    # Reload correction
    correction = storage.load_correction(correction.id)
    
    # Verify all gates passed
    assert correction.gate1.status == "pass"
    assert correction.gate2a.status == "pass"
    assert correction.gate2a.confidence == 0.92
    assert correction.gate2b is None  # Skipped due to high confidence
    assert correction.final_status == "pending"  # Waiting for Gate 3


@pytest.mark.asyncio
async def test_pipeline_reject_gate1(pipeline_instance, storage):
    """Test correction rejected at Gate 1."""
    correction = storage.create_correction(
        user_id="teen",
        content="harmful content"
    )
    
    # Mock Gate 1 - reject
    with patch('gates.gate1_sanity.validate_gate1', new_callable=AsyncMock) as mock_gate1:
        mock_gate1.return_value = ("reject", "Contains harmful content")
        
        await pipeline_instance.process_correction(correction)
    
    # Reload correction
    correction = storage.load_correction(correction.id)
    
    # Verify rejection at Gate 1
    assert correction.gate1.status == "reject"
    assert correction.final_status == "rejected_gate1"
    assert correction.gate2a is None  # Never reached Gate 2


@pytest.mark.asyncio
async def test_pipeline_low_confidence_calls_gate2b(pipeline_instance, storage):
    """Test that low confidence in Gate 2a triggers Gate 2b."""
    correction = storage.create_correction(
        user_id="mom",
        content="Some uncertain fact"
    )
    
    # Mock Gate 1 - pass
    with patch('gates.gate1_sanity.validate_gate1', new_callable=AsyncMock) as mock_gate1:
        mock_gate1.return_value = ("pass", "Coherent")
        
        # Mock Gate 2a - pass with LOW confidence
        with patch('gates.gate2a_local_factcheck.validate_gate2a', new_callable=AsyncMock) as mock_gate2a:
            mock_gate2a.return_value = ("pass", 0.65, "Uncertain", False)
            
            # Mock Gate 2b - pass
            with patch('gates.gate2b_claude.validate_gate2b', new_callable=AsyncMock) as mock_gate2b:
                mock_gate2b.return_value = ("pass", "Factually accurate")
                
                # Mock notification
                with patch.object(pipeline_instance.notifier, 'notify_learning_review'):
                    await pipeline_instance.process_correction(correction)
    
    # Reload correction
    correction = storage.load_correction(correction.id)
    
    # Verify Gate 2b was called
    assert correction.gate2a.confidence == 0.65
    assert correction.gate2b is not None
    assert correction.gate2b.status == "pass"
    assert correction.final_status == "pending"


@pytest.mark.asyncio
async def test_pipeline_personal_info_skips_gate2b(pipeline_instance, storage):
    """Test that personal info skips Gate 2b even with low confidence."""
    correction = storage.create_correction(
        user_id="mom",
        content="Ma fille s'appelle Alice"
    )
    
    # Mock Gate 1 - pass
    with patch('gates.gate1_sanity.validate_gate1', new_callable=AsyncMock) as mock_gate1:
        mock_gate1.return_value = ("pass", "Coherent")
        
        # Mock Gate 2a - will detect personal info
        with patch('gates.gate2a_local_factcheck.validate_gate2a', new_callable=AsyncMock) as mock_gate2a:
            mock_gate2a.return_value = ("pass", 1.0, "Personal information - auto-approved", True)
            
            # Mock notification
            with patch.object(pipeline_instance.notifier, 'notify_learning_review'):
                await pipeline_instance.process_correction(correction)
    
    # Reload correction
    correction = storage.load_correction(correction.id)
    
    # Verify personal info detected and Gate 2b skipped
    assert correction.personal_info is True
    assert correction.gate2b is None  # Skipped
    assert correction.final_status == "pending"


@pytest.mark.asyncio
async def test_pipeline_gate1_error(pipeline_instance, storage):
    """Test pipeline behavior when Gate 1 has an error."""
    correction = storage.create_correction(
        user_id="mom",
        content="Some content"
    )
    
    # Mock Gate 1 - error
    with patch('gates.gate1_sanity.validate_gate1', new_callable=AsyncMock) as mock_gate1:
        mock_gate1.return_value = ("error", "LLM Sidecar timeout")
        
        await pipeline_instance.process_correction(correction)
    
    # Reload correction
    correction = storage.load_correction(correction.id)
    
    # Verify error handling
    assert correction.gate1.status == "error"
    assert correction.final_status == "gate1_error"
    assert correction.gate2a is None  # Pipeline stopped


@pytest.mark.asyncio
async def test_pipeline_notification_sent(pipeline_instance, storage):
    """Test that notification is sent when reaching Gate 3."""
    correction = storage.create_correction(
        user_id="mom",
        content="Normal correction"
    )
    
    # Mock all gates to pass
    with patch('gates.gate1_sanity.validate_gate1', new_callable=AsyncMock) as mock_gate1:
        mock_gate1.return_value = ("pass", "OK")
        
        with patch('gates.gate2a_local_factcheck.validate_gate2a', new_callable=AsyncMock) as mock_gate2a:
            mock_gate2a.return_value = ("pass", 0.85, "OK", False)
            
            # Mock notification
            with patch.object(pipeline_instance.notifier, 'notify_learning_review') as mock_notify:
                await pipeline_instance.process_correction(correction)
                
                # Verify notification was called
                mock_notify.assert_called_once_with(count=1)
