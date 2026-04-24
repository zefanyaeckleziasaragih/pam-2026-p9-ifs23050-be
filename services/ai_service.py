import logging
import requests
import json
from config import Config

logger = logging.getLogger(__name__)

# Sistem prompt diringkas: buang penjelasan redundan, hapus field "description"
# dari output JSON agar model tidak generate teks tambahan yang tidak perlu.
SYSTEM_PROMPT = (
    "Username generator. Output ONLY valid JSON, no markdown:\n"
    '{"usernames":["u1","u2"]}\n'
    "Rules: no spaces, alphanumeric/underscore/dot, 4-20 chars, no offensive words.\n"
    "Style guide: gaming=edgy/cool, professional=clean/formal, cute=kawaii, "
    "aesthetic=artsy, funny=witty, minimalist=short/simple, fantasy=mythical, tech=geeky."
)

REQUIRED_KEYS = {"usernames"}


def _validate_result(result: dict, total: int) -> dict:
    missing = REQUIRED_KEYS - result.keys()
    if missing:
        raise ValueError(f"Incomplete JSON from LLM — missing keys: {missing}")

    if not isinstance(result["usernames"], list) or len(result["usernames"]) == 0:
        raise ValueError("usernames must be a non-empty list")

    sanitized = [str(u).strip() for u in result["usernames"] if str(u).strip()]
    result["usernames"] = sanitized[:total]
    result.setdefault("description", "")

    return result


def generate_usernames(keyword: str, style: str, total: int) -> dict:
    # User prompt singkat: hanya data yang berubah-ubah per request
    user_prompt = f"keyword:{keyword} style:{style} count:{total}"

    payload = {
        "token": Config.LLM_TOKEN,
        "chat": f"{SYSTEM_PROMPT}\n\n{user_prompt}",
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

    # Strip markdown fences jika model mengabaikan instruksi
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip()

    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("LLM returned invalid JSON: %s | raw: %s", e, content[:500])
        raise ValueError("LLM returned invalid JSON") from e

    return _validate_result(result, total)
