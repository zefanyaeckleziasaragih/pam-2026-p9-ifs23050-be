import logging
import requests
import json
from config import Config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a creative username generator assistant.
Given a keyword/theme and style, generate unique, creative usernames.

Respond ONLY with valid JSON, no markdown, no explanation:
{
  "usernames": ["username1", "username2", "username3"],
  "description": "Brief explanation of the naming style and choices made"
}

Rules for username generation:
- No spaces (use underscores or camelCase if needed)
- Alphanumeric characters, underscores, dots allowed
- Length: 4–20 characters each
- No offensive or inappropriate words
- Make them memorable and unique
- Match the requested style (gaming = edgy/cool, professional = clean/formal, cute = kawaii/sweet, etc.)
"""

REQUIRED_KEYS = {"usernames", "description"}


def _validate_result(result: dict, total: int) -> dict:
    missing = REQUIRED_KEYS - result.keys()
    if missing:
        raise ValueError(f"Incomplete JSON from LLM — missing keys: {missing}")

    if not isinstance(result["usernames"], list) or len(result["usernames"]) == 0:
        raise ValueError("usernames must be a non-empty list")

    # Sanitize usernames: strip whitespace, remove empties
    sanitized = []
    for u in result["usernames"]:
        u = str(u).strip()
        if u:
            sanitized.append(u)

    result["usernames"] = sanitized[:total]  # cap at requested total
    result["description"] = str(result.get("description", "")).strip()

    return result


def generate_usernames(keyword: str, style: str, total: int) -> dict:
    user_prompt = (
        f"Keyword/theme: {keyword}\n"
        f"Style: {style}\n"
        f"Generate exactly {total} unique usernames.\n"
        f"Respond ONLY with valid JSON as specified."
    )

    full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"

    payload = {
        "token": Config.LLM_TOKEN,
        "chat": full_prompt,
    }

    response = requests.post(
        f"{Config.LLM_BASE_URL}/llm/chat",
        json=payload,
        timeout=60,
    )

    if response.status_code != 200:
        logger.error(
            "LLM API error: status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        raise Exception("LLM API returned non-200 status")

    data = response.json()

    # Extract text content from various response shapes
    content = None
    if isinstance(data, dict):
        content = (
            data.get("response")
            or data.get("message")
            or data.get("content")
            or data.get("text")
        )
        if not content and "choices" in data:
            content = data["choices"][0]["message"]["content"]
    elif isinstance(data, str):
        content = data

    if not content:
        logger.error("Unexpected LLM response structure: %s", str(data)[:500])
        raise ValueError("Cannot extract content from LLM response")

    # Strip markdown fences
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip()

    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(
            "LLM returned invalid JSON: %s | raw: %s", e, content[:500]
        )
        raise ValueError("LLM returned invalid JSON") from e

    return _validate_result(result, total)
