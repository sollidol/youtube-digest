import httpx

OEMBED_URL = "https://www.youtube.com/oembed"


async def fetch_video_meta(video_id: str) -> dict:
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(OEMBED_URL, params={"url": url, "format": "json"})
            resp.raise_for_status()
            data = resp.json()
            return {
                "title": data.get("title", "Неизвестно"),
                "channel": data.get("author_name", "Неизвестно"),
            }
    except Exception:
        return {"title": "Неизвестно", "channel": "Неизвестно"}
