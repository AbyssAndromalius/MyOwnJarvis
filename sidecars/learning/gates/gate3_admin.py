"""
Gate 3: Admin Approval
Manual review by administrator before applying correction to memory.
"""
import logging
import httpx

from storage import Storage, Correction
from notifier import Notifier
from config import get_config

logger = logging.getLogger(__name__)


async def submit_to_gate3(correction: Correction, storage: Storage, notifier: Notifier):
    """
    Submit correction to Gate 3 (admin approval).
    
    Args:
        correction: Correction to submit
        storage: Storage instance
        notifier: Notifier instance
    """
    # Update correction status to pending Gate 3
    storage.update_gate3_pending(correction)
    
    logger.info(f"Correction {correction.id} submitted to Gate 3 (admin approval)")
    
    # Send desktop notification
    notifier.notify_learning_review(count=1)


async def apply_to_memory(correction: Correction) -> str | None:
    """
    Apply approved correction to memory via LLM Sidecar.
    
    Args:
        correction: Approved correction to apply
        
    Returns:
        Memory ID if successful, None if failed
    """
    config = get_config()
    memory_url = f"{config.llm_sidecar.base_url}/memory/add"
    
    payload = {
        "user_id": correction.user_id,
        "content": correction.content,
        "source": "learning_correction",
        "metadata": {
            "correction_id": correction.id,
            "submitted_at": correction.submitted_at
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=config.llm_sidecar.timeout_seconds) as client:
            response = await client.post(memory_url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            memory_id = data.get("id") or data.get("memory_id")
            
            logger.info(f"Correction {correction.id} applied to memory: {memory_id}")
            return memory_id
    
    except Exception as e:
        logger.error(f"Failed to apply correction {correction.id} to memory: {e}")
        return None
