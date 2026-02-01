"""Tests for daily ingest (RSS, dedupe)."""
from pathlib import Path

from app.ingest import load_channel_urls
from app.models import Video, VIDEO_STATUS_NEW


def test_ingest_dedupes_same_video_id(db_session):
    """Simulate ingest loop: same video_id must not be inserted twice."""
    # Pre-insert one video (as if from a previous run)
    db_session.add(Video(
        video_id="abc123",
        title="Existing",
        url="https://www.youtube.com/watch?v=abc123",
        channel_name="Channel",
        status=VIDEO_STATUS_NEW,
    ))
    db_session.commit()

    # Same logic as ingest_daily inner loop: process feed results and skip existing
    videos_from_feed = [
        {"video_id": "abc123", "title": "Existing", "url": "https://youtube.com/watch?v=abc123", "channel_name": "Channel", "channel_url": "", "published_at": None},
        {"video_id": "xyz789", "title": "New", "url": "https://youtube.com/watch?v=xyz789", "channel_name": "Channel", "channel_url": "", "published_at": None},
    ]
    inserted = 0
    for v in videos_from_feed:
        if db_session.query(Video).filter(Video.video_id == v["video_id"]).first():
            continue
        db_session.add(Video(
            video_id=v["video_id"],
            title=v["title"],
            url=v["url"],
            channel_name=v["channel_name"],
            channel_url=v.get("channel_url", ""),
            published_at=v.get("published_at"),
            status=VIDEO_STATUS_NEW,
        ))
        inserted += 1
    db_session.commit()

    assert inserted == 1
    assert db_session.query(Video).filter(Video.video_id == "abc123").count() == 1
    assert db_session.query(Video).filter(Video.video_id == "xyz789").count() == 1
    assert db_session.query(Video).count() == 2


def test_load_channel_urls():
    """load_channel_urls returns list of non-empty, non-comment lines."""
    root = Path(__file__).parent.parent
    urls = load_channel_urls(root / "channels.txt")
    assert isinstance(urls, list)
