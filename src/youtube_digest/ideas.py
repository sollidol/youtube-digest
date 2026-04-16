from datetime import datetime, timezone
from pathlib import Path

import httpx

from .config import settings

IDEAS_DIR = Path("/opt/dev/knowledge_base/ideas")

EXTRACT_PROMPT = """\
Из саммари видео извлеки конкретные идеи, которые можно применить в бизнесе или рабочих процессах.

Контекст владельца:
- КДМ (мебельный бизнес, франчайзи Вардек)
- Фарфор (франшиза общепита)
- AI/автоматизация бизнес-процессов
- Удалённое управление бизнесами

Правила:
- Только конкретные, применимые идеи (не общие советы типа «надо больше продавать»)
- Каждая идея = одно конкретное действие или изменение
- Если применимых идей нет — верни пустой список
- Формат: JSON-массив объектов, каждый с полями: "title" (короткое название), "description" (2-3 предложения: что сделать и зачем), "tags" (массив из: kdm, farfor, ai, marketing, sales, management, strategy)

Отвечай ТОЛЬКО валидным JSON, без markdown-обёрток.
"""

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def extract_ideas(summary: str, video_title: str, channel: str) -> list[dict]:
    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": EXTRACT_PROMPT},
            {"role": "user", "content": f"Видео: {video_title}\nКанал: {channel}\n\nСаммари:\n{summary}"},
        ],
        "max_tokens": 2048,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=60) as client:
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

    import json
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict) and "ideas" in parsed:
        return parsed["ideas"]
    return []


def save_idea(
    title: str,
    description: str,
    tags: list[str],
    source_url: str,
    source_title: str,
    source_channel: str,
) -> Path:
    IDEAS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)

    slug = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)[:50].strip()
    slug = slug.replace(" ", "-").lower() or "idea"
    filename = f"{now.strftime('%Y%m%d')}_{slug}.md"
    path = IDEAS_DIR / filename

    counter = 1
    while path.exists():
        path = IDEAS_DIR / f"{now.strftime('%Y%m%d')}_{slug}_{counter}.md"
        counter += 1

    tags_str = ", ".join(tags)
    content = f"""---
title: "{title}"
status: new
tags: [{tags_str}]
source: {source_url}
source_title: "{source_title}"
source_channel: "{source_channel}"
date: {now.strftime('%Y-%m-%d')}
---

{description}
"""
    path.write_text(content, encoding="utf-8")
    return path
