import json
import logging
from typing import Optional
from groq import Groq
from app.core.config import get_settings, get_config

logger  = logging.getLogger(__name__)
_client: Optional[Groq] = None


def get_llm_client() -> Optional[Groq]:
    global _client
    if _client is None:
        key = get_settings().groq_api_key
        if key:
            _client = Groq(api_key=key)
        else:
            logger.warning("GROQ_API_KEY not set — LLM calls disabled")
    return _client


def get_model() -> str:
    return get_config().get("apis", {}).get("groq", {}).get("model", "llama-3.3-70b-versatile")


def call_llm(prompt: str, max_tokens: int = 300, json_mode: bool = True) -> tuple[dict | str, int]:
    client = get_llm_client()
    if not client:
        return ({} if json_mode else ""), 0

    kwargs = dict(
        model=get_model(),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp   = client.chat.completions.create(**kwargs)
        text   = resp.choices[0].message.content
        tokens = resp.usage.total_tokens
        return (json.loads(text) if json_mode else text.strip()), tokens
    except json.JSONDecodeError as e:
        logger.warning(f"LLM bad JSON: {e}")
        return {}, 0
    except Exception as e:
        logger.warning(f"LLM call failed: {e}")
        return ({} if json_mode else ""), 0
