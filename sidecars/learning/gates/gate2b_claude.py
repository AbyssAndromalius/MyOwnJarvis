"""
Gate 2b: Claude API Fact-Check
Fallback fact-checking using Claude API when local LLM has low confidence.
Never receives personal information.
"""
import logging
from typing import Tuple
from anthropic import AsyncAnthropic
import json

from config import get_config, get_claude_api_key

logger = logging.getLogger(__name__)


GATE2B_PROMPT = """Is the following statement factually accurate? Answer only with JSON: {"verdict": "pass"|"reject", "reason": "..."}

Statement: {content}"""


async def validate_gate2b(content: str) -> Tuple[str, str]:
    """
    Validate correction through Gate 2b (Claude API fact-check).
    
    Args:
        content: The correction content to validate (fact only, no personal context)
        
    Returns:
        Tuple of (status, reason)
        status: "pass", "reject", or "error"
        reason: Explanation of the decision
    """
    config = get_config()
    api_key = get_claude_api_key()
    
    # If API key not configured, pass by default
    if not api_key:
        logger.warning("Gate 2b: Claude API key not configured, auto-passing")
        return "pass", "gate2b_unavailable - API key not configured"
    
    try:
        client = AsyncAnthropic(
            api_key=api_key,
            timeout=config.claude.timeout_seconds
        )
        
        # Call Claude API
        message = await client.messages.create(
            model=config.claude.model,
            max_tokens=config.claude.max_tokens,
            messages=[{
                "role": "user",
                "content": GATE2B_PROMPT.format(content=content)
            }]
        )
        
        # Extract response
        response_text = message.content[0].text
        
        # Parse JSON response
        try:
            # Try to extract JSON if Claude added extra text
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "{" in response_text and "}" in response_text:
                # Extract just the JSON object
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                response_text = response_text[json_start:json_end]
            
            result = json.loads(response_text)
            verdict = result.get("verdict", "reject")
            reason = result.get("reason", "No reason provided")
            
            if verdict not in ["pass", "reject"]:
                logger.warning(f"Invalid verdict from Claude: {verdict}, defaulting to reject")
                return "reject", f"Invalid Claude response: {reason}"
            
            logger.info(f"Gate 2b result: {verdict} - {reason}")
            return verdict, reason
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {response_text}")
            return "error", f"Claude response parsing error: {str(e)}"
    
    except Exception as e:
        # If Claude API is unreachable or errors, pass by default (don't block indefinitely)
        logger.warning(f"Gate 2b: Claude API error: {e}, auto-passing")
        return "pass", f"gate2b_unavailable - {str(e)}"
