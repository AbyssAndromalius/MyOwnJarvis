"""
Gate 1: Sanity Check
Validates correction coherence and safety using local LLM.
"""
import httpx
import logging
import json
from typing import Tuple

from config import get_config

logger = logging.getLogger(__name__)


GATE1_PROMPT = """You are a safety and coherence validator for user corrections to a personal assistant.

Evaluate the following correction and respond ONLY with JSON in this exact format:
{"verdict": "pass", "reason": "explanation"}
OR
{"verdict": "reject", "reason": "explanation"}

Evaluate for:
1. Internal coherence - does the correction make logical sense?
2. Safety - is it free of harmful, abusive, or dangerous content?

Correction to evaluate: {content}

Remember: Respond ONLY with valid JSON, no additional text."""


async def validate_gate1(content: str) -> Tuple[str, str]:
    """
    Validate correction through Gate 1 (sanity check).
    
    Args:
        content: The correction content to validate
        
    Returns:
        Tuple of (status, reason)
        status: "pass", "reject", or "error"
        reason: Explanation of the decision
    """
    config = get_config()
    
    # Build the prompt
    prompt = GATE1_PROMPT.format(content=content)
    
    # Prepare request to LLM Sidecar
    llm_url = f"{config.llm_sidecar.base_url}/chat"
    payload = {
        "user_id": config.llm_sidecar.gate_user_id,
        "message": prompt
    }
    
    try:
        async with httpx.AsyncClient(timeout=config.llm_sidecar.timeout_seconds) as client:
            response = await client.post(llm_url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            llm_response = data.get("response", "")
            
            # Parse the JSON response from LLM
            try:
                # Try to extract JSON if LLM added extra text
                if "```json" in llm_response:
                    json_start = llm_response.find("```json") + 7
                    json_end = llm_response.find("```", json_start)
                    llm_response = llm_response[json_start:json_end].strip()
                elif "```" in llm_response:
                    json_start = llm_response.find("```") + 3
                    json_end = llm_response.find("```", json_start)
                    llm_response = llm_response[json_start:json_end].strip()
                
                result = json.loads(llm_response)
                verdict = result.get("verdict", "reject")
                reason = result.get("reason", "No reason provided")
                
                if verdict not in ["pass", "reject"]:
                    logger.warning(f"Invalid verdict from LLM: {verdict}, defaulting to reject")
                    return "reject", f"Invalid LLM response: {reason}"
                
                logger.info(f"Gate 1 result: {verdict} - {reason}")
                return verdict, reason
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {llm_response}")
                return "error", f"LLM response parsing error: {str(e)}"
    
    except httpx.TimeoutException:
        logger.error("Gate 1: LLM Sidecar timeout")
        return "error", "LLM Sidecar timeout"
    
    except httpx.HTTPError as e:
        logger.error(f"Gate 1: LLM Sidecar HTTP error: {e}")
        return "error", f"LLM Sidecar unreachable: {str(e)}"
    
    except Exception as e:
        logger.error(f"Gate 1: Unexpected error: {e}")
        return "error", f"Unexpected error: {str(e)}"
