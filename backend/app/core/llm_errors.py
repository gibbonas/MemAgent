"""
LLM / Gemini API error handling - MemAgent

Parses error responses and detects retryable conditions (503, 429).
"""

import json
import re


# HTTP status codes that warrant a retry
RETRYABLE_STATUS_CODES = (503, 429)


def parse_llm_error(exception: BaseException) -> str:
    """
    Extract a user-friendly message from an LLM/Gemini API exception.

    Handles JSON error bodies like:
      {"error": {"code": 503, "message": "...", "status": "UNAVAILABLE"}}

    Returns the inner message when present, otherwise a generic fallback.
    """
    raw = str(exception).strip()
    if not raw:
        return "Something went wrong. Please try again."

    data = None
    # Try JSON (double-quoted)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Try embedded {...} in the string
    if data is None:
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                # str() of a Python dict uses single quotes - try ast.literal_eval
                try:
                    import ast
                    data = ast.literal_eval(match.group(0))
                except (ValueError, SyntaxError):
                    data = None
    # Extract message from nested error
    if isinstance(data, dict):
        error = data.get("error") if isinstance(data.get("error"), dict) else None
        if error and isinstance(error.get("message"), str):
            return error["message"].strip()
        if isinstance(data.get("message"), str):
            return data["message"].strip()
    # Fallback: short single-line use as-is; otherwise generic message
    if len(raw) < 400 and "\n" not in raw:
        return raw
    return "The AI service is temporarily unavailable. Please try again in a moment."


def is_retryable_llm_error(exception: BaseException) -> bool:
    """
    Return True if the exception indicates a retryable condition (e.g. 503, 429).
    """
    raw = str(exception)
    for code in RETRYABLE_STATUS_CODES:
        if str(code) in raw or f'"{code}"' in raw:
            return True
    if "UNAVAILABLE" in raw.upper() or "RESOURCE_EXHAUSTED" in raw.upper():
        return True
    return False
