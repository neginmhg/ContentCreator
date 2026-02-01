"""Import existing sources from text files to database."""
from pathlib import Path

from app.db import SessionLocal
from app.models import ChannelSource, BlogSource
from app.config import CHANNELS_FILE, BLOGS_FILE


def import_channel_sources():
    """Import channel sources from channels.txt."""
    db = SessionLocal()
    try:
        if CHANNELS_FILE.exists():
            lines = CHANNELS_FILE.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Check if already exists
                    existing = db.query(ChannelSource).filter(ChannelSource.url == line).first()
                    if not existing:
                        db.add(ChannelSource(url=line, is_active=True))
            db.commit()
            print(f"Imported channel sources from {CHANNELS_FILE}")
        else:
            print(f"Channel file {CHANNELS_FILE} not found")
    finally:
        db.close()


def import_blog_sources():
    """Import blog sources from blogs.txt."""
    db = SessionLocal()
    try:
        if BLOGS_FILE.exists():
            lines = BLOGS_FILE.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Check if already exists
                    existing = db.query(BlogSource).filter(BlogSource.url == line).first()
                    if not existing:
                        db.add(BlogSource(url=line, is_active=True))
            db.commit()
            print(f"Imported blog sources from {BLOGS_FILE}")
        else:
            print(f"Blog file {BLOGS_FILE} not found")
    finally:
        db.close()


def main():
    """Import all sources from text files."""
    print("Importing sources from text files to database...")
    import_channel_sources()
    import_blog_sources()
    print("Import completed!")


if __name__ == "__main__":
    main()
