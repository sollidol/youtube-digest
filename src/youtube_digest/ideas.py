from datetime import datetime, timezone
from pathlib import Path

IDEAS_FILE = Path("/opt/dev/knowledge_base/ideas-backlog.md")


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
