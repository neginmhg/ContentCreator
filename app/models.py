"""SQLAlchemy models for videos, transcripts, and drafts."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Video status enum as string values
VIDEO_STATUS_NEW = "NEW"
VIDEO_STATUS_PROCESSING = "PROCESSING"
VIDEO_STATUS_READY = "READY"
VIDEO_STATUS_MANUAL_REVIEW = "MANUAL_REVIEW"
VIDEO_STATUS_POSTED = "POSTED"
VIDEO_STATUS_SKIPPED = "SKIPPED"

# Processing step values (when status == PROCESSING). Keys stored in Video.processing_step.
PROCESSING_STEP_DOWNLOAD = "download"
PROCESSING_STEP_CONVERT = "convert"
PROCESSING_STEP_CHUNK = "chunk"
PROCESSING_STEP_TRANSCRIBE = "transcribe"
PROCESSING_STEP_DRAFT = "draft"
PROCESSING_STEP_LABELS = {
    PROCESSING_STEP_DOWNLOAD: "Downloading audio",
    PROCESSING_STEP_CONVERT: "Converting audio",
    PROCESSING_STEP_CHUNK: "Chunking audio",
    PROCESSING_STEP_TRANSCRIBE: "Transcribing",
    PROCESSING_STEP_DRAFT: "Generating draft",
}


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(32), unique=True, nullable=False, index=True)
    title = Column(String(512), nullable=False)
    url = Column(String(512), nullable=False)
    channel_name = Column(String(256), nullable=False)
    channel_url = Column(String(512), nullable=True)
    published_at = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=False, default=VIDEO_STATUS_NEW, index=True)
    processing_step = Column(String(64), nullable=True)  # current step when status == PROCESSING
    last_completed_step = Column(String(64), nullable=True)  # last successfully completed step
    error_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transcript = relationship("Transcript", back_populates="video", uselist=False)
    draft = relationship("Draft", back_populates="video", uselist=False)


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(32), ForeignKey("videos.video_id"), unique=True, nullable=False, index=True)
    text = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="PENDING")  # PENDING, OK, FAILED
    model_used = Column(String(128), nullable=True)
    language = Column(String(16), nullable=True)
    word_count = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    video = relationship("Video", back_populates="transcript")


# Blog status enum as string values
BLOG_STATUS_NEW = "NEW"
BLOG_STATUS_PROCESSING = "PROCESSING"
BLOG_STATUS_READY = "READY"
BLOG_STATUS_MANUAL_REVIEW = "MANUAL_REVIEW"
BLOG_STATUS_POSTED = "POSTED"
BLOG_STATUS_SKIPPED = "SKIPPED"

# Blog processing step values (when status == PROCESSING). Keys stored in Blog.processing_step.
BLOG_PROCESSING_STEP_FETCH = "fetch"
BLOG_PROCESSING_STEP_DRAFT = "draft"
BLOG_PROCESSING_STEP_LABELS = {
    BLOG_PROCESSING_STEP_FETCH: "Fetching blog content",
    BLOG_PROCESSING_STEP_DRAFT: "Generating draft",
}


class ChannelSource(Base):
    __tablename__ = "channel_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(512), nullable=False, unique=True)
    name = Column(String(256), nullable=True)  # Optional display name
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BlogSource(Base):
    __tablename__ = "blog_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(512), nullable=False, unique=True)
    name = Column(String(256), nullable=True)  # Optional display name
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Blog(Base):
    __tablename__ = "blogs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    blog_id = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(512), nullable=False)
    url = Column(String(512), nullable=False)
    source_name = Column(String(256), nullable=False)
    source_url = Column(String(512), nullable=True)
    published_at = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=False, default=BLOG_STATUS_NEW, index=True)
    processing_step = Column(String(64), nullable=True)  # current step when status == PROCESSING
    last_completed_step = Column(String(64), nullable=True)  # last successfully completed step
    error_reason = Column(Text, nullable=True)
    content = Column(Text, nullable=True)  # Full blog content
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    draft = relationship("BlogDraft", back_populates="blog", uselist=False)


class BlogDraft(Base):
    __tablename__ = "blog_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    blog_id = Column(String(64), ForeignKey("blogs.blog_id"), unique=True, nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    blog = relationship("Blog", back_populates="draft")


class Draft(Base):
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(32), ForeignKey("videos.video_id"), unique=True, nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    video = relationship("Video", back_populates="draft")
