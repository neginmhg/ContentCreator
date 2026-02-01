"""Optional dev seed: create sample rows for testing."""
import sys
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, init_db
from app.models import Video, Transcript, Draft, VIDEO_STATUS_NEW, VIDEO_STATUS_READY


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        # Avoid duplicate sample
        existing = db.query(Video).filter(Video.video_id == "seed_dev_001").first()
        if existing:
            print("Seed already present (video_id=seed_dev_001). Skipping.")
            return
        now = datetime.utcnow()
        v = Video(
            video_id="seed_dev_001",
            title="Sample: How to Build a MVP in 48 Hours",
            url="https://www.youtube.com/watch?v=seed_dev_001",
            channel_name="Dev Tips",
            channel_url="https://www.youtube.com/@DevTips",
            published_at=now - timedelta(days=1),
            status=VIDEO_STATUS_NEW,
        )
        db.add(v)
        db.commit()
        # One READY sample
        v2 = Video(
            video_id="seed_dev_002",
            title="Sample: The Future of AI in 2025",
            url="https://www.youtube.com/watch?v=seed_dev_002",
            channel_name="Tech Channel",
            published_at=now - timedelta(days=2),
            status=VIDEO_STATUS_READY,
        )
        db.add(v2)
        db.commit()
        t = Transcript(video_id="seed_dev_002", text="This is a sample transcript for testing.", status="OK", word_count=7)
        d = Draft(video_id="seed_dev_002", text="Key takeaway from Tech Channel's video:\n- Sample point one\n- Sample point two\n\nWhat would you add? #AI #Tech #2025")
        db.add(t)
        db.add(d)
        db.commit()
        print("Created sample videos: seed_dev_001 (NEW), seed_dev_002 (READY with transcript and draft).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
