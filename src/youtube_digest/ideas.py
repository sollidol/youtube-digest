from datetime import datetime, timezone
from pathlib import Path

import httpx

from .config import settings

IDEAS_FILE = Path("/opt/dev/knowledge_base/ideas-backlog.md")

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


def save_ideas(
    ideas: list[dict],
    source_url: str,
    source_title: str,
    source_channel: str,
) -> int:
    IDEAS_FILE.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)

    if not IDEAS_FILE.exists():
        IDEAS_FILE.write_text("# Бэклог идей\n\n", encoding="utf-8")

    tags_fmt = lambda t: " ".join(f"`#{x}`" for x in t)
    lines = [f"\n## [{source_title}]({source_url}) — {source_channel} ({now.strftime('%Y-%m-%d')})\n"]
    for idea in ideas:
        lines.append(f"- [ ] **{idea['title']}** — {idea['description']} {tags_fmt(idea.get('tags', []))}")

    with IDEAS_FILE.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return len(ideas)
