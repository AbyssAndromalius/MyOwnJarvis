"""
Gate 2a: Local Fact-Check
Validates factual accuracy using local LLM with confidence scoring.
Automatically passes personal information without LLM call.
"""
import httpx
import logging
import json
from typing import Tuple

from config import get_config

logger = logging.getLogger(__name__)


GATE2A_PROMPT = """You are a fact-checking assistant for user corrections.

Evaluate the factual accuracy of the following statement and respond ONLY with JSON in this exact format:
{"verdict": "pass", "confidence": 0.85, "reason": "explanation"}
OR
{"verdict": "reject", "confidence": 0.90, "reason": "explanation"}

Guidelines:
- "pass" if the statement is factually plausible or likely true
- "reject" if the statement is clearly false or implausible
- confidence: 0.0 to 1.0, how certain you are of your verdict
- Be generous with uncertainty - use lower confidence when unsure

Statement to evaluate: {content}

Remember: Respond ONLY with valid JSON, no additional text."""


def is_personal_info(content: str) -> bool:
    """
    Check if content contains personal information keywords.
    
    Args:
        content: Content to check
        
    Returns:
        True if personal information detected, False otherwise
    """
    config = get_config()
    content_lower = content.lower()
    
    for keyword in config.gates.personal_info_keywords:
        if keyword.lower() in content_lower:
            logger.info(f"Personal info detected (keyword: {keyword})")
            return True
    
    return False


async def validate_gate2a(content: str) -> Tuple[str, float, str, bool]:
    """
    Validate correction through Gate 2a (local fact-check).
    
    Args:
        content: The correction content to validate
        
    Returns:
        Tuple of (status, confidence, reason, is_personal)
        status: "pass", "reject", or "error"
        confidence: 0.0 to 1.0
        reason: Explanation of the decision
        is_personal: True if personal info detected
    """
    # Check for personal information first
    if is_personal_info(content):
        logger.info("Gate 2a: Personal info detected, auto-passing")
        return "pass", 1.0, "Personal information - auto-approved", True
    
    config = get_config()
    
    # Build the prompt
    prompt = GATE2A_PROMPT.format(content=content)
    
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
                confidence = float(result.get("confidence", 0.5))
                reason = result.get("reason", "No reason provided")
                
                # Validate confidence range
                confidence = max(0.0, min(1.0, confidence))
                
                if verdict not in ["pass", "reject"]:
                    logger.warning(f"Invalid verdict from LLM: {verdict}, defaulting to reject")
                    return "reject", confidence, f"Invalid LLM response: {reason}", False
                
                logger.info(f"Gate 2a result: {verdict} (confidence: {confidence:.2f}) - {reason}")
                return verdict, confidence, reason, False
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse LLM response: {llm_response}")
                return "error", 0.0, f"LLM response parsing error: {str(e)}", False
    
    except httpx.TimeoutException:
        logger.error("Gate 2a: LLM Sidecar timeout")
        return "error", 0.0, "LLM Sidecar timeout", False
    
    except httpx.HTTPError as e:
        logger.error(f"Gate 2a: LLM Sidecar HTTP error: {e}")
        return "error", 0.0, f"LLM Sidecar unreachable: {str(e)}", False
    
    except Exception as e:
        logger.error(f"Gate 2a: Unexpected error: {e}")
        return "error", 0.0, f"Unexpected error: {str(e)}", False
