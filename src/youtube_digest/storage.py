from datetime import datetime, timezone
from pathlib import Path

from .config import settings


def save_digest(
    video_id: str,
    title: str,
    channel: str,
    summary: str,
) -> Path:
    now = datetime.now(timezone.utc)
    month_dir = settings.output_dir / now.strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)

    slug = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)[:60].strip()
    slug = slug.replace(" ", "-").lower() or video_id
    filename = f"{now.strftime('%Y%m%d')}_{slug}.md"
    path = month_dir / filename

    url = f"https://www.youtube.com/watch?v={video_id}"
    content = f"""---
title: "{title}"
channel: "{channel}"
url: {url}
date: {now.strftime('%Y-%m-%d %H:%M')} UTC
---

{summary}
"""
    path.write_text(content, encoding="utf-8")
    return path
