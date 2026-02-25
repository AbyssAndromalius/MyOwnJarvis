"""
Tests for storage management and state transitions.
"""
import pytest
from pathlib import Path
from storage import Storage, Correction


@pytest.fixture
def storage(tmp_path):
    """Create a storage instance with temporary directory."""
    storage = Storage(base_path=str(tmp_path / "learning"))
    return storage


def test_storage_directory_creation(tmp_path):
    """Test that storage creates required directories."""
    base_path = tmp_path / "learning"
    storage = Storage(base_path=str(base_path))
    
    assert (base_path / "pending").exists()
    assert (base_path / "approved").exists()
    assert (base_path / "rejected").exists()
    assert (base_path / "applied").exists()


def test_create_correction(storage):
    """Test creating a new correction."""
    correction = storage.create_correction(
        user_id="mom",
        content="Test correction",
        source="user_correction"
    )
    
    assert correction.id is not None
    assert correction.user_id == "mom"
    assert correction.content == "Test correction"
    assert correction.final_status == "processing"
    assert correction.personal_info is False


def test_save_and_load_correction(storage):
    """Test saving and loading a correction."""
    correction = storage.create_correction(
        user_id="teen",
        content="Test content"
    )
    
    storage.save_correction(correction)
    
    loaded = storage.load_correction(correction.id)
    
    assert loaded is not None
    assert loaded.id == correction.id
    assert loaded.user_id == correction.user_id
    assert loaded.content == correction.content


def test_load_nonexistent_correction(storage):
    """Test loading a correction that doesn't exist."""
    loaded = storage.load_correction("nonexistent-id")
    assert loaded is None


def test_update_gate1(storage):
    """Test updating Gate 1 result."""
    correction = storage.create_correction(user_id="mom", content="Test")
    storage.save_correction(correction)
    
    storage.update_gate1(correction, "pass", "Coherent and safe")
    
    loaded = storage.load_correction(correction.id)
    assert loaded.gate1 is not None
    assert loaded.gate1.status == "pass"
    assert loaded.gate1.reason == "Coherent and safe"
    assert loaded.gate1.processed_at is not None


def test_update_gate1_reject(storage):
    """Test Gate 1 rejection updates final status."""
    correction = storage.create_correction(user_id="mom", content="Test")
    storage.save_correction(correction)
    
    storage.update_gate1(correction, "reject", "Harmful content")
    
    loaded = storage.load_correction(correction.id)
    assert loaded.final_status == "rejected_gate1"


def test_update_gate2a(storage):
    """Test updating Gate 2a result."""
    correction = storage.create_correction(user_id="mom", content="Test")
    storage.save_correction(correction)
    
    storage.update_gate2a(correction, "pass", 0.92, "Factually plausible")
    
    loaded = storage.load_correction(correction.id)
    assert loaded.gate2a is not None
    assert loaded.gate2a.status == "pass"
    assert loaded.gate2a.confidence == 0.92
    assert loaded.gate2a.reason == "Factually plausible"


def test_update_gate2b(storage):
    """Test updating Gate 2b result."""
    correction = storage.create_correction(user_id="mom", content="Test")
    storage.save_correction(correction)
    
    storage.update_gate2b(correction, "pass", "Verified by Claude")
    
    loaded = storage.load_correction(correction.id)
    assert loaded.gate2b is not None
    assert loaded.gate2b.status == "pass"
    assert loaded.gate2b.reason == "Verified by Claude"


def test_update_gate3_pending(storage):
    """Test marking correction as pending Gate 3."""
    correction = storage.create_correction(user_id="mom", content="Test")
    storage.save_correction(correction)
    
    storage.update_gate3_pending(correction)
    
    loaded = storage.load_correction(correction.id)
    assert loaded.gate3 is not None
    assert loaded.gate3.status == "pending"
    assert loaded.final_status == "pending"


def test_update_gate3_approve(storage):
    """Test approving a correction at Gate 3."""
    correction = storage.create_correction(user_id="mom", content="Test")
    storage.update_gate3_pending(correction)
    
    storage.update_gate3_review(correction, "approve", "dad")
    
    loaded = storage.load_correction(correction.id)
    assert loaded.gate3.status == "approved"
    assert loaded.gate3.reviewer == "dad"
    assert loaded.final_status == "approved"


def test_update_gate3_reject(storage):
    """Test rejecting a correction at Gate 3."""
    correction = storage.create_correction(user_id="mom", content="Test")
    storage.update_gate3_pending(correction)
    
    storage.update_gate3_review(correction, "reject", "dad", "Incorrect information")
    
    loaded = storage.load_correction(correction.id)
    assert loaded.gate3.status == "rejected"
    assert loaded.gate3.reviewer == "dad"
    assert loaded.gate3.reject_reason == "Incorrect information"
    assert loaded.final_status == "rejected_gate3"


def test_mark_applied(storage):
    """Test marking correction as applied to memory."""
    correction = storage.create_correction(user_id="mom", content="Test")
    storage.update_gate3_pending(correction)
    storage.update_gate3_review(correction, "approve", "dad")
    
    memory_id = "mem-123"
    storage.mark_applied(correction, memory_id)
    
    loaded = storage.load_correction(correction.id)
    assert loaded.final_status == "applied"
    assert loaded.memory_id == memory_id
    assert loaded.applied_at is not None


def test_list_pending_empty(storage):
    """Test listing pending corrections when none exist."""
    pending = storage.list_pending()
    assert len(pending) == 0


def test_list_pending_with_items(storage):
    """Test listing pending corrections."""
    # Create and save multiple corrections
    correction1 = storage.create_correction(user_id="mom", content="Test 1")
    storage.update_gate3_pending(correction1)
    
    correction2 = storage.create_correction(user_id="teen", content="Test 2")
    storage.update_gate3_pending(correction2)
    
    # Create a rejected one (should not appear in pending)
    correction3 = storage.create_correction(user_id="mom", content="Test 3")
    storage.update_gate1(correction3, "reject", "Bad")
    
    pending = storage.list_pending()
    
    assert len(pending) == 2
    assert any(c.id == correction1.id for c in pending)
    assert any(c.id == correction2.id for c in pending)
    assert not any(c.id == correction3.id for c in pending)


def test_get_pending_count(storage):
    """Test getting count of pending corrections."""
    assert storage.get_pending_count() == 0
    
    correction = storage.create_correction(user_id="mom", content="Test")
    storage.update_gate3_pending(correction)
    
    assert storage.get_pending_count() == 1


def test_file_moves_between_directories(storage):
    """Test that correction file moves between directories based on status."""
    correction = storage.create_correction(user_id="mom", content="Test")
    
    # Initially processing - no specific directory yet
    storage.save_correction(correction)
    
    # Move to pending
    storage.update_gate3_pending(correction)
    file_path = storage._get_file_path(correction.id, "pending")
    assert file_path.exists()
    
    # Move to approved
    storage.update_gate3_review(correction, "approve", "dad")
    file_path = storage._get_file_path(correction.id, "approved")
    assert file_path.exists()
    
    # Old file should be removed
    old_path = storage._get_file_path(correction.id, "pending")
    assert not old_path.exists()


def test_rejected_corrections_in_rejected_directory(storage):
    """Test that rejected corrections go to rejected directory."""
    correction = storage.create_correction(user_id="mom", content="Test")
    storage.save_correction(correction)
    
    storage.update_gate1(correction, "reject", "Bad")
    
    file_path = storage._get_file_path(correction.id, "rejected_gate1")
    assert file_path.exists()
    assert file_path.parent.name == "rejected"


def test_health_check(storage):
    """Test storage health check."""
    assert storage.health_check() is True


def test_correction_with_all_gates(storage):
    """Test a correction going through all gates."""
    correction = storage.create_correction(user_id="mom", content="Test")
    storage.save_correction(correction)
    
    # Gate 1
    storage.update_gate1(correction, "pass", "OK")
    
    # Gate 2a
    storage.update_gate2a(correction, "pass", 0.75, "Low confidence")
    
    # Gate 2b (triggered by low confidence)
    storage.update_gate2b(correction, "pass", "Verified")
    
    # Gate 3
    storage.update_gate3_pending(correction)
    storage.update_gate3_review(correction, "approve", "dad")
    
    # Apply to memory
    storage.mark_applied(correction, "mem-456")
    
    # Verify final state
    loaded = storage.load_correction(correction.id)
    assert loaded.gate1.status == "pass"
    assert loaded.gate2a.status == "pass"
    assert loaded.gate2b.status == "pass"
    assert loaded.gate3.status == "approved"
    assert loaded.final_status == "applied"
    assert loaded.memory_id == "mem-456"
