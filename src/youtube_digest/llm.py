import json
import logging
import re

import httpx

from .config import settings
from .prompts import SYSTEM_PROMPT_TEMPLATE, USER_PROMPT_TEMPLATE

log = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


async def analyze(
    transcript: str,
    title: str = "Неизвестно",
    channel: str = "Неизвестно",
) -> dict:
    user_msg = USER_PROMPT_TEMPLATE.format(
        title=title,
        channel=channel,
        transcript=transcript[:120_000],
    )

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        owner_context=settings.owner_context,
        tags=settings.idea_tags,
    )

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 16384,
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

        if resp.status_code == 402:
            raise LLMError("💳 Баланс OpenRouter пуст. Пополни на openrouter.ai/credits")
        if resp.status_code == 429:
            raise LLMError("⏳ Лимит запросов OpenRouter. Подожди пару минут.")
        if resp.status_code == 401:
            raise LLMError("🔑 Невалидный API-ключ OpenRouter.")
        resp.raise_for_status()

        data = resp.json()

    error = data.get("error")
    if error:
        code = error.get("code", 0)
        msg = error.get("message", "")
        if code == 402 or "credit" in msg.lower() or "balance" in msg.lower():
            raise LLMError("💳 Баланс OpenRouter пуст. Пополни на openrouter.ai/credits")
        raise LLMError(f"OpenRouter: {msg}")

    content = data["choices"][0]["message"]["content"]
    log.debug("LLM raw response length: %d", len(content) if content else 0)

    if not content:
        raise LLMError(f"Пустой ответ от LLM. Data: {json.dumps(data)[:300]}")

    return _extract_json(content)


class LLMError(Exception):
    """Error with a user-friendly message."""
