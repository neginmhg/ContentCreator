"""Blog ingestion: read blog_sources table, fetch RSS feeds, upsert blog posts."""
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import feedparser
import requests
from sqlalchemy.orm import Session

from app.config import BLOGS_FILE
from app.models import Blog, BLOG_STATUS_NEW, BlogSource


def _generate_blog_id(url: str) -> str:
    """Generate a unique blog_id from URL using MD5 hash."""
    return hashlib.md5(url.encode()).hexdigest()[:32]


def _clean_html(html: str) -> str:
    """Remove HTML tags and clean up content."""
    # Simple HTML tag removal
    clean = re.sub(r'<[^>]+>', '', html)
    # Clean up whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def _extract_content(entry) -> Optional[str]:
    """Extract content from RSS entry, trying multiple fields."""
    # Try content field
    content = getattr(entry, 'content', None)
    if content and isinstance(content, list) and content:
        content = content[0]
        if hasattr(content, 'value'):
            return _clean_html(content.value)
    
    # Try summary field
    summary = getattr(entry, 'summary', None)
    if summary:
        return _clean_html(summary)
    
    # Try description field
    description = getattr(entry, 'description', None)
    if description:
        return _clean_html(description)
    
    return None


def _parse_rss_blogs(feed_url: str, source_name: str, source_url: str) -> list[dict]:
    """Return list of dicts with blog_id, title, url, source_name, source_url, published_at, content."""
    feed = feedparser.parse(feed_url)
    entries = getattr(feed, "entries", []) or []
    feed_feed = getattr(feed, "feed", None)
    source_name = source_name or (getattr(feed_feed, "title", None) if feed_feed else None) or "Unknown"
    out = []
    
    for e in entries:
        link = getattr(e, "link", None)
        if not link:
            continue
            
        blog_id = _generate_blog_id(link)
        title = getattr(e, "title", None) or ""
        published = getattr(e, "published_parsed", None)
        if published:
            try:
                published_at = datetime(*published[:6])
            except Exception:
                published_at = None
        else:
            published_at = None
            
        content = _extract_content(e)
        
        out.append({
            "blog_id": blog_id,
            "title": title,
            "url": link,
            "source_name": source_name,
            "source_url": source_url or "",
            "published_at": published_at,
            "content": content,
        })
    return out


def load_blog_sources(db: Session) -> list[str]:
    """Load active blog RSS URLs from database."""
    sources = db.query(BlogSource).filter(BlogSource.is_active == True).all()
    return [source.url for source in sources]


def ingest_blogs(db: Session) -> tuple[int, int]:
    """
    For each active blog RSS feed in database: fetch, insert new blog posts (dedupe by blog_id).
    Returns (inserted_count, error_count).
    """
    urls = load_blog_sources(db)
    inserted = 0
    errors = 0
    
    for feed_url in urls:
        try:
            blogs = _parse_rss_blogs(feed_url, "", feed_url)
        except Exception as e:
            print(f"Error fetching {feed_url}: {e}")
            errors += 1
            continue
            
        for b in blogs:
            existing = db.query(Blog).filter(Blog.blog_id == b["blog_id"]).first()
            if existing:
                continue
                
            db.add(Blog(
                blog_id=b["blog_id"],
                title=b["title"],
                url=b["url"],
                source_name=b["source_name"],
                source_url=b["source_url"],
                published_at=b["published_at"],
                content=b["content"],
                status=BLOG_STATUS_NEW,
            ))
            inserted += 1
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Database commit error: {e}")
        errors += 1
        
    return inserted, errors
