"""Backend-only OpenAI-compatible chat completions adapter with graceful fallback."""
import json
import os
import re
from typing import Any
import httpx

TIERS = {
    "cheap": ("AI_CHEAP_BASE_URL", "AI_CHEAP_MODEL", "AI_CHEAP_API_KEY"),
    "standard": ("AI_STANDARD_BASE_URL", "AI_STANDARD_MODEL", "AI_STANDARD_API_KEY"),
    "premium": ("AI_PREMIUM_BASE_URL", "AI_PREMIUM_MODEL", "AI_PREMIUM_API_KEY"),
}


def tier_is_configured(tier: str) -> bool:
    base_key, model_key, _ = TIERS[tier]
    return bool(os.getenv(base_key, "").strip() and os.getenv(model_key, "").strip())


def configured_tiers() -> dict[str, bool]:
    return {tier: tier_is_configured(tier) for tier in TIERS}


def chat_json(tier: str, system_prompt: str, user_prompt: str, timeout: float = 22.0) -> Any | None:
    if not tier_is_configured(tier):
        return None
    base_key, model_key, api_key_key = TIERS[tier]
    base_url = os.getenv(base_key, "").strip().rstrip("/")
    model = os.getenv(model_key, "").strip()
    api_key = os.getenv(api_key_key, "").strip()
    if base_url.endswith("/chat/completions"):
        url = base_url
    else:
        url = base_url + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        content = str(content).strip()
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
        return json.loads(content)
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        # Do not log request headers, API keys, or model responses that may contain user data.
        return None


def comparison_summary(properties: list[dict], user_goal: str | None = None) -> tuple[str | None, str]:
    prompt = {"properties": properties, "user_goal": user_goal or "Find the best overall fit."}
    system = (
        "Compare the provided synthetic property records. Return JSON with one string field 'summary'. "
        "Use only supplied facts, identify trade-offs, and do not claim a property is objectively best without context. "
        "Do not invent facts or market claims. Write in Persian."
    )
    result = chat_json("premium", system, json.dumps(prompt, ensure_ascii=False), timeout=28.0)
    if isinstance(result, dict) and isinstance(result.get("summary"), str):
        return result["summary"][:3000], "ai"
    return None, "unavailable"
