import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

CACHE_PATH = Path("/opt/dev/projects/youtube-digest/var/cache.json")


def _load() -> dict:
    if CACHE_PATH.exists():
        try:
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            # Convert selected lists back to sets
            for vid, entry in data.items():
                if "selected" in entry:
                    entry["selected"] = set(entry["selected"])
            return data
        except Exception as e:
            log.warning("Failed to load cache: %s", e)
    return {}


def _save(cache: dict):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Convert sets to lists for JSON
    serializable = {}
    for vid, entry in cache.items():
        serializable[vid] = {
            k: sorted(v) if isinstance(v, set) else v
            for k, v in entry.items()
        }
    CACHE_PATH.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")


# In-memory cache backed by file
digest_cache: dict[str, dict] = _load()


def put(video_id: str, data: dict):
    digest_cache[video_id] = data
    _save(digest_cache)


def get(video_id: str) -> dict | None:
    return digest_cache.get(video_id)


def update(video_id: str):
    _save(digest_cache)
