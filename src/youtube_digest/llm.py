import httpx

from .config import settings
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def summarize(
    transcript: str,
    title: str = "Неизвестно",
    channel: str = "Неизвестно",
) -> str:
    user_msg = USER_PROMPT_TEMPLATE.format(
        title=title,
        channel=channel,
        transcript=transcript[:120_000],
    )

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 2048,
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=120) as client:
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

    return data["choices"][0]["message"]["content"]
