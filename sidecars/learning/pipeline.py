"""
Learning Pipeline Orchestrator
Manages the 3-gate validation pipeline: Gate 1 -> Gate 2a -> Gate 2b (conditional) -> Gate 3
"""
import logging
from storage import Storage, Correction
from notifier import Notifier
from gates.gate1_sanity import validate_gate1
from gates.gate2a_local_factcheck import validate_gate2a
from gates.gate2b_claude import validate_gate2b
from gates.gate3_admin import submit_to_gate3
from config import get_config

logger = logging.getLogger(__name__)


class Pipeline:
    """Manages the learning correction validation pipeline."""
    
    def __init__(self, storage: Storage, notifier: Notifier):
        """
        Initialize pipeline.
        
        Args:
            storage: Storage instance
            notifier: Notifier instance
        """
        self.storage = storage
        self.notifier = notifier
        self.config = get_config()
    
    async def process_correction(self, correction: Correction):
        """
        Process a correction through the full pipeline.
        
        Args:
            correction: Correction to process
        """
        logger.info(f"Starting pipeline for correction {correction.id}")
        
        # Gate 1: Sanity Check
        gate1_status, gate1_reason = await validate_gate1(correction.content)
        self.storage.update_gate1(correction, gate1_status, gate1_reason)
        
        if gate1_status == "reject":
            logger.info(f"Correction {correction.id} rejected at Gate 1")
            return
        
        if gate1_status == "error":
            logger.error(f"Correction {correction.id} failed at Gate 1 with error")
            return
        
        logger.info(f"Correction {correction.id} passed Gate 1")
        
        # Gate 2a: Local Fact-Check
        gate2a_status, gate2a_confidence, gate2a_reason, is_personal = await validate_gate2a(
            correction.content
        )
        
        # Mark personal info flag
        correction.personal_info = is_personal
        
        self.storage.update_gate2a(correction, gate2a_status, gate2a_confidence, gate2a_reason)
        
        if gate2a_status == "reject":
            logger.info(f"Correction {correction.id} rejected at Gate 2a")
            return
        
        if gate2a_status == "error":
            logger.error(f"Correction {correction.id} failed at Gate 2a with error")
            return
        
        logger.info(f"Correction {correction.id} passed Gate 2a (confidence: {gate2a_confidence:.2f})")
        
        # Gate 2b: Claude API Fallback (only if confidence < threshold AND not personal info)
        threshold = self.config.gates.gate2a_confidence_threshold
        
        if is_personal:
            logger.info(f"Correction {correction.id} contains personal info, skipping Gate 2b")
        elif gate2a_confidence >= threshold:
            logger.info(f"Correction {correction.id} confidence >= {threshold}, skipping Gate 2b")
        else:
            logger.info(f"Correction {correction.id} confidence < {threshold}, calling Gate 2b")
            gate2b_status, gate2b_reason = await validate_gate2b(correction.content)
            self.storage.update_gate2b(correction, gate2b_status, gate2b_reason)
            
            if gate2b_status == "reject":
                logger.info(f"Correction {correction.id} rejected at Gate 2b")
                return
            
            logger.info(f"Correction {correction.id} passed Gate 2b")
        
        # Gate 3: Admin Approval
        await submit_to_gate3(correction, self.storage, self.notifier)
        logger.info(f"Correction {correction.id} submitted to Gate 3 (pending admin approval)")
