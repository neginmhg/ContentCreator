"""Daily ingest: read channel_sources table, fetch YouTube RSS per channel, upsert videos."""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import feedparser
import requests
from sqlalchemy.orm import Session

from app.config import CHANNELS_FILE
from app.models import Video, VIDEO_STATUS_NEW, ChannelSource

# YouTube RSS base
YOUTUBE_RSS_BASE = "https://www.youtube.com/feeds/videos.xml?channel_id="

# Patterns to extract channel_id from YouTube pages
CHANNEL_ID_IN_META = re.compile(r'"channelId"\s*:\s*"([^"]+)"')
CHANNEL_ID_UC = re.compile(r"(UC[\w-]{22})")


def _channel_id_from_url(session: Session, url: str) -> Optional[str]:
    """Resolve channel URL to channel_id. Returns None on failure."""
    url = url.strip()
    if not url or url.startswith("#"):
        return None

    # Already have channel_id in path: /channel/UCxxxx
    m = re.search(r"youtube\.com/channel/(UC[\w-]{22})", url, re.IGNORECASE)
    if m:
        return m.group(1)

    # channel_id in query: ?channel_id=UCxxxx
    parsed = urlparse(url)
    if "channel_id" in (parsed.query or ""):
        for part in parsed.query.split("&"):
            if part.startswith("channel_id="):
                return part.split("=", 1)[1].strip()

    # @handle or /c/name: fetch page and scrape channel_id
    try:
        resp = session.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (compatible; ContentBot/1.0)"})
        resp.raise_for_status()
        text = resp.text
    except Exception:
        return None

    for pattern in (CHANNEL_ID_IN_META, CHANNEL_ID_UC):
        m = pattern.search(text)
        if m:
            cid = m.group(1) if m.lastindex else m.group(0)
            if cid.startswith("UC") and len(cid) == 24:
                return cid
    return None


def _rss_url_for_channel(channel_id: str) -> str:
    return f"{YOUTUBE_RSS_BASE}{channel_id}"


def _parse_rss_videos(feed_url: str, channel_name: str, channel_url: str) -> list[dict]:
    """Return list of dicts with video_id, title, url, channel_name, channel_url, published_at."""
    feed = feedparser.parse(feed_url)
    entries = getattr(feed, "entries", []) or []
    feed_feed = getattr(feed, "feed", None)
    channel_name = channel_name or (getattr(feed_feed, "title", None) if feed_feed else None) or "Unknown"
    out = []
    for e in entries:
        video_id = (
            getattr(e, "yt_videoid", None)
            or (e.get("link") and ("v=" in e["link"]) and e["link"].split("v=")[-1].split("&")[0])
            or (e.get("id") and "video:" in str(e.get("id")) and str(e["id"]).split("video:")[-1].strip())
        )
        if not video_id or len(video_id) > 20:
            continue
        # Normalize id (no & or extra params)
        if "&" in video_id:
            video_id = video_id.split("&")[0]
        video_id = video_id.strip()
        title = getattr(e, "title", None) or ""
        link = getattr(e, "link", None) or f"https://www.youtube.com/watch?v={video_id}"
        published = getattr(e, "published_parsed", None)
        if published:
            try:
                published_at = datetime(*published[:6])
            except Exception:
                published_at = None
        else:
            published_at = None
        out.append({
            "video_id": video_id,
            "title": title,
            "url": link,
            "channel_name": channel_name,
            "channel_url": channel_url or "",
            "published_at": published_at,
        })
    return out


def load_channel_sources(db: Session) -> list[str]:
    """Load active channel URLs from database."""
    sources = db.query(ChannelSource).filter(ChannelSource.is_active == True).all()
    return [source.url for source in sources]


def ingest_daily(db: Session) -> tuple[int, int]:
    """
    For each active channel in database: resolve to RSS, fetch, insert new videos (dedupe by video_id).
    Returns (inserted_count, error_channel_count).
    """
    urls = load_channel_sources(db)
    inserted = 0
    errors = 0
    session = requests.Session()
    for raw_url in urls:
        channel_id = _channel_id_from_url(session, raw_url)
        if not channel_id:
            errors += 1
            continue
        rss_url = _rss_url_for_channel(channel_id)
        try:
            videos = _parse_rss_videos(rss_url, "", raw_url)
        except Exception:
            errors += 1
            continue
        for v in videos:
            existing = db.query(Video).filter(Video.video_id == v["video_id"]).first()
            if existing:
                continue
            db.add(Video(
                video_id=v["video_id"],
                title=v["title"],
                url=v["url"],
                channel_name=v["channel_name"],
                channel_url=v["channel_url"],
                published_at=v["published_at"],
                status=VIDEO_STATUS_NEW,
            ))
            inserted += 1
    db.commit()
    return inserted, errors
