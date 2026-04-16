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
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    log.debug("LLM raw response length: %d", len(content) if content else 0)

    if not content:
        raise ValueError(f"Empty LLM response. Full data: {json.dumps(data)[:500]}")

    return _extract_json(content)
