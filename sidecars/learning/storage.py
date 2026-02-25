"""
Storage management for learning corrections using JSON files.
"""
import json
import uuid
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from config import get_config


class GateResult(BaseModel):
    """Result from a gate validation."""
    status: str  # pass, reject, pending, error
    reason: str | None = None
    confidence: float | None = None
    processed_at: str | None = None


class Gate3Details(BaseModel):
    """Gate 3 specific details."""
    status: str  # pending, approved, rejected
    submitted_at: str
    reviewed_at: str | None = None
    reviewer: str | None = None
    reject_reason: str | None = None


class Correction(BaseModel):
    """Learning correction model."""
    id: str
    user_id: str
    content: str
    source: str = "user_correction"
    submitted_at: str
    personal_info: bool = False
    gate1: GateResult | None = None
    gate2a: GateResult | None = None
    gate2b: GateResult | None = None
    gate3: Gate3Details | None = None
    applied_at: str | None = None
    final_status: str = "processing"  # processing, pending, rejected_gate1, rejected_gate2a, rejected_gate2b, rejected_gate3, approved
    memory_id: str | None = None


class Storage:
    """Manages storage of learning corrections in JSON files."""
    
    def __init__(self, base_path: str | None = None):
        """
        Initialize storage.
        
        Args:
            base_path: Base path for storage directories (from config if None)
        """
        if base_path is None:
            config = get_config()
            base_path = config.storage.base_path
        
        self.base_path = Path(__file__).parent / base_path
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create storage directories if they don't exist."""
        for subdir in ['pending', 'approved', 'rejected', 'applied']:
            (self.base_path / subdir).mkdir(parents=True, exist_ok=True)
    
    def _get_file_path(self, correction_id: str, status: str) -> Path:
        """
        Get the file path for a correction based on its status.
        
        Args:
            correction_id: Correction ID
            status: Correction status (pending, approved, rejected, applied)
            
        Returns:
            Path to the correction file
        """
        # Map final_status to directory
        if status.startswith("rejected"):
            directory = "rejected"
        elif status == "approved":
            directory = "approved"
        elif status == "pending":
            directory = "pending"
        elif status == "applied":
            directory = "applied"
        else:
            directory = "pending"  # Default for processing
        
        return self.base_path / directory / f"{correction_id}.json"
    
    def _find_correction_file(self, correction_id: str) -> Optional[Path]:
        """
        Find a correction file across all directories.
        
        Args:
            correction_id: Correction ID to find
            
        Returns:
            Path to the file if found, None otherwise
        """
        for subdir in ['pending', 'approved', 'rejected', 'applied']:
            file_path = self.base_path / subdir / f"{correction_id}.json"
            if file_path.exists():
                return file_path
        return None
    
    def create_correction(self, user_id: str, content: str, source: str = "user_correction") -> Correction:
        """
        Create a new correction.
        
        Args:
            user_id: User who submitted the correction
            content: Correction content
            source: Source of the correction
            
        Returns:
            New Correction object
        """
        correction = Correction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            content=content,
            source=source,
            submitted_at=datetime.now(timezone.utc).isoformat(),
            final_status="processing"
        )
        return correction
    
    def save_correction(self, correction: Correction):
        """
        Save a correction to disk.
        
        Args:
            correction: Correction to save
        """
        # Determine the file path based on status
        file_path = self._get_file_path(correction.id, correction.final_status)
        
        # If the correction exists in another directory, remove it
        old_path = self._find_correction_file(correction.id)
        if old_path and old_path != file_path and old_path.exists():
            old_path.unlink()
        
        # Save to the appropriate directory
        with open(file_path, 'w') as f:
            json.dump(correction.model_dump(), f, indent=2)
    
    def load_correction(self, correction_id: str) -> Optional[Correction]:
        """
        Load a correction from disk.
        
        Args:
            correction_id: ID of the correction to load
            
        Returns:
            Correction object if found, None otherwise
        """
        file_path = self._find_correction_file(correction_id)
        if not file_path:
            return None
        
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        return Correction(**data)
    
    def list_pending(self) -> List[Correction]:
        """
        List all corrections pending admin approval (Gate 3).
        
        Returns:
            List of pending corrections
        """
        pending_dir = self.base_path / 'pending'
        corrections = []
        
        if pending_dir.exists():
            for file_path in pending_dir.glob('*.json'):
                with open(file_path, 'r') as f:
                    data = json.load(f)
                corrections.append(Correction(**data))
        
        return sorted(corrections, key=lambda c: c.submitted_at)
    
    def update_gate1(self, correction: Correction, status: str, reason: str):
        """Update Gate 1 result."""
        correction.gate1 = GateResult(
            status=status,
            reason=reason,
            processed_at=datetime.now(timezone.utc).isoformat()
        )
        
        if status == "reject":
            correction.final_status = "rejected_gate1"
        elif status == "error":
            correction.final_status = "gate1_error"
        
        self.save_correction(correction)
    
    def update_gate2a(self, correction: Correction, status: str, confidence: float, reason: str):
        """Update Gate 2a result."""
        correction.gate2a = GateResult(
            status=status,
            confidence=confidence,
            reason=reason,
            processed_at=datetime.now(timezone.utc).isoformat()
        )
        
        if status == "reject":
            correction.final_status = "rejected_gate2a"
        
        self.save_correction(correction)
    
    def update_gate2b(self, correction: Correction, status: str, reason: str):
        """Update Gate 2b result."""
        correction.gate2b = GateResult(
            status=status,
            reason=reason,
            processed_at=datetime.now(timezone.utc).isoformat()
        )
        
        if status == "reject":
            correction.final_status = "rejected_gate2b"
        
        self.save_correction(correction)
    
    def update_gate3_pending(self, correction: Correction):
        """Mark correction as pending Gate 3 approval."""
        correction.gate3 = Gate3Details(
            status="pending",
            submitted_at=datetime.now(timezone.utc).isoformat()
        )
        correction.final_status = "pending"
        self.save_correction(correction)
    
    def update_gate3_review(self, correction: Correction, action: str, reviewer: str, reason: str | None = None):
        """Update Gate 3 with approval or rejection."""
        if correction.gate3 is None:
            correction.gate3 = Gate3Details(
                status="pending",
                submitted_at=datetime.now(timezone.utc).isoformat()
            )
        
        correction.gate3.status = "approved" if action == "approve" else "rejected"
        correction.gate3.reviewed_at = datetime.now(timezone.utc).isoformat()
        correction.gate3.reviewer = reviewer
        if reason:
            correction.gate3.reject_reason = reason
        
        correction.final_status = "approved" if action == "approve" else "rejected_gate3"
        self.save_correction(correction)
    
    def mark_applied(self, correction: Correction, memory_id: str):
        """Mark correction as applied to memory."""
        correction.applied_at = datetime.now(timezone.utc).isoformat()
        correction.memory_id = memory_id
        correction.final_status = "applied"
        self.save_correction(correction)
    
    def get_pending_count(self) -> int:
        """Get count of pending corrections."""
        return len(self.list_pending())
    
    def health_check(self) -> bool:
        """
        Check if storage is accessible.
        
        Returns:
            True if storage is accessible, False otherwise
        """
        try:
            self._ensure_directories()
            return True
        except Exception:
            return False
