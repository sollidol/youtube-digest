import re

from youtube_transcript_api import YouTubeTranscriptApi


VIDEO_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?.*?v=|shorts/|embed/|live/))"
    r"([A-Za-z0-9_-]{11})"
)


def extract_video_id(url: str) -> str | None:
    m = VIDEO_ID_RE.search(url)
    return m.group(1) if m else None


def fetch_transcript(video_id: str) -> str:
    ytt = YouTubeTranscriptApi()
    transcript = ytt.fetch(video_id, languages=["ru", "en"])
    return " ".join(seg.text for seg in transcript)
