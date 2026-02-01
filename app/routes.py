"""FastAPI routes and Jinja2 UI."""
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db import get_db, SessionLocal, init_db
from app.models import (
    Video,
    Transcript,
    Draft,
    Blog,
    BlogDraft,
    ChannelSource,
    BlogSource,
    VIDEO_STATUS_NEW,
    VIDEO_STATUS_PROCESSING,
    VIDEO_STATUS_READY,
    VIDEO_STATUS_MANUAL_REVIEW,
    VIDEO_STATUS_POSTED,
    VIDEO_STATUS_SKIPPED,
    PROCESSING_STEP_LABELS,
    BLOG_STATUS_NEW,
    BLOG_STATUS_PROCESSING,
    BLOG_STATUS_READY,
    BLOG_STATUS_MANUAL_REVIEW,
    BLOG_STATUS_POSTED,
    BLOG_STATUS_SKIPPED,
    BLOG_PROCESSING_STEP_LABELS,
)
from app.generate import run_generate_pipeline
from app.blog_generate import run_blog_generate_pipeline
from app.ingest import ingest_daily
from app.blog_ingest import ingest_blogs

router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Pydantic models for bulk delete requests
class BulkDeleteVideos(BaseModel):
    video_ids: list[str]

class BulkDeleteBlogs(BaseModel):
    blog_ids: list[str]

ORDERED_STATUSES = [
    VIDEO_STATUS_NEW,
    VIDEO_STATUS_PROCESSING,
    VIDEO_STATUS_READY,
    VIDEO_STATUS_MANUAL_REVIEW,
    VIDEO_STATUS_POSTED,
    VIDEO_STATUS_SKIPPED,
]

BLOG_ORDERED_STATUSES = [
    BLOG_STATUS_NEW,
    BLOG_STATUS_PROCESSING,
    BLOG_STATUS_READY,
    BLOG_STATUS_MANUAL_REVIEW,
    BLOG_STATUS_POSTED,
    BLOG_STATUS_SKIPPED,
]


def _run_pipeline_in_background(video_id: str) -> None:
    db = SessionLocal()
    try:
        run_generate_pipeline(db, video_id)
    finally:
        db.close()


def _run_blog_pipeline_in_background(blog_id: str) -> None:
    db = SessionLocal()
    try:
        run_blog_generate_pipeline(db, blog_id)
    finally:
        db.close()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, tab: str = None, db: Session = Depends(get_db)):
    # Get videos
    videos = db.query(Video).order_by(Video.published_at.desc().nullslast(), Video.created_at.desc()).all()
    by_status: dict[str, list[Video]] = {s: [] for s in ORDERED_STATUSES}
    for v in videos:
        if v.status in by_status:
            by_status[v.status].append(v)
    counts = {s: len(by_status[s]) for s in ORDERED_STATUSES}
    
    # Get blogs
    blogs = db.query(Blog).order_by(Blog.published_at.desc().nullslast(), Blog.created_at.desc()).all()
    blogs_by_status: dict[str, list[Blog]] = {s: [] for s in BLOG_ORDERED_STATUSES}
    for b in blogs:
        if b.status in blogs_by_status:
            blogs_by_status[b.status].append(b)
    blog_counts = {s: len(blogs_by_status[s]) for s in BLOG_ORDERED_STATUSES}
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "by_status": by_status,
            "counts": counts,
            "status_order": ORDERED_STATUSES,
            "processing_step_labels": PROCESSING_STEP_LABELS,
            "blogs_by_status": blogs_by_status,
            "blog_counts": blog_counts,
            "blog_status_order": BLOG_ORDERED_STATUSES,
            "blog_processing_step_labels": BLOG_PROCESSING_STEP_LABELS,
            "active_tab": tab or "videos",
        },
    )


@router.get("/video/{video_id}", response_class=HTMLResponse)
def video_detail(request: Request, video_id: str, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.video_id == video_id).first()
    if not video:
        return HTMLResponse("<h1>Video not found</h1>", status_code=404)
    trans = db.query(Transcript).filter(Transcript.video_id == video_id).first()
    draft = db.query(Draft).filter(Draft.video_id == video_id).first()
    return templates.TemplateResponse(
        "video_detail.html",
        {
            "request": request,
            "video": video,
            "transcript": trans,
            "draft": draft,
            "processing_step_labels": PROCESSING_STEP_LABELS,
        },
    )


@router.post("/video/{video_id}/generate")
def start_generate(video_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.video_id == video_id).first()
    if not video:
        return HTMLResponse("<h1>Video not found</h1>", status_code=404)
    if video.status not in (VIDEO_STATUS_NEW, VIDEO_STATUS_MANUAL_REVIEW):
        return RedirectResponse(url=f"/video/{video_id}", status_code=303)
    background_tasks.add_task(_run_pipeline_in_background, video_id)
    return RedirectResponse(url=f"/video/{video_id}", status_code=303)


@router.post("/video/{video_id}/mark-posted")
def mark_posted(video_id: str, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.video_id == video_id).first()
    if not video:
        return HTMLResponse("<h1>Video not found</h1>", status_code=404)
    video.status = VIDEO_STATUS_POSTED
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.post("/video/{video_id}/mark-skipped")
def mark_skipped(video_id: str, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.video_id == video_id).first()
    if not video:
        return HTMLResponse("<h1>Video not found</h1>", status_code=404)
    video.status = VIDEO_STATUS_SKIPPED
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.post("/video/{video_id}/delete")
def delete_video(video_id: str, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.video_id == video_id).first()
    if not video:
        return HTMLResponse("<h1>Video not found</h1>", status_code=404)
    
    # Delete related transcript and draft if they exist
    transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
    if transcript:
        db.delete(transcript)
    
    draft = db.query(Draft).filter(Draft.video_id == video_id).first()
    if draft:
        db.delete(draft)
    
    db.delete(video)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.get("/video/{video_id}/refresh")
def refresh_fragment(video_id: str, db: Session = Depends(get_db)):
    """Return status and current processing step for auto-refresh / polling."""
    video = db.query(Video).filter(Video.video_id == video_id).first()
    if not video:
        return {"status": "NOT_FOUND"}
    step_label = PROCESSING_STEP_LABELS.get(video.processing_step, "Processing") if video.processing_step else None
    return {
        "status": video.status,
        "processing_step": video.processing_step,
        "processing_step_label": step_label,
        "error_reason": video.error_reason,
    }


@router.post("/fetch-videos")
def fetch_videos(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Fetch latest videos from channels.txt."""
    def _fetch():
        try:
            ingest_daily(db)
        except Exception as e:
            print(f"Error fetching videos: {e}")
    
    background_tasks.add_task(_fetch)
    return RedirectResponse(url="/", status_code=303)


@router.post("/fetch-blogs")
def fetch_blogs(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Fetch latest blogs from blogs.txt."""
    def _fetch():
        try:
            ingest_blogs(db)
        except Exception as e:
            print(f"Error fetching blogs: {e}")
    
    background_tasks.add_task(_fetch)
    return RedirectResponse(url="/?tab=blogs", status_code=303)


@router.get("/blog/{blog_id}", response_class=HTMLResponse)
def blog_detail(request: Request, blog_id: str, db: Session = Depends(get_db)):
    blog = db.query(Blog).filter(Blog.blog_id == blog_id).first()
    if not blog:
        return HTMLResponse("<h1>Blog not found</h1>", status_code=404)
    draft = db.query(BlogDraft).filter(BlogDraft.blog_id == blog_id).first()
    return templates.TemplateResponse(
        "blog_detail.html",
        {
            "request": request,
            "blog": blog,
            "draft": draft,
            "blog_processing_step_labels": BLOG_PROCESSING_STEP_LABELS,
        },
    )


@router.post("/blog/{blog_id}/generate")
def start_blog_generate(blog_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    blog = db.query(Blog).filter(Blog.blog_id == blog_id).first()
    if not blog:
        return HTMLResponse("<h1>Blog not found</h1>", status_code=404)
    if blog.status not in (BLOG_STATUS_NEW, BLOG_STATUS_MANUAL_REVIEW):
        return RedirectResponse(url=f"/blog/{blog_id}", status_code=303)
    background_tasks.add_task(_run_blog_pipeline_in_background, blog_id)
    return RedirectResponse(url=f"/blog/{blog_id}", status_code=303)


@router.post("/blog/{blog_id}/mark-posted")
def mark_blog_posted(blog_id: str, db: Session = Depends(get_db)):
    blog = db.query(Blog).filter(Blog.blog_id == blog_id).first()
    if not blog:
        return HTMLResponse("<h1>Blog not found</h1>", status_code=404)
    blog.status = BLOG_STATUS_POSTED
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.post("/blog/{blog_id}/mark-skipped")
def mark_blog_skipped(blog_id: str, db: Session = Depends(get_db)):
    blog = db.query(Blog).filter(Blog.blog_id == blog_id).first()
    if not blog:
        return HTMLResponse("<h1>Blog not found</h1>", status_code=404)
    blog.status = BLOG_STATUS_SKIPPED
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.post("/blog/{blog_id}/delete")
def delete_blog(blog_id: str, db: Session = Depends(get_db)):
    blog = db.query(Blog).filter(Blog.blog_id == blog_id).first()
    if not blog:
        return HTMLResponse("<h1>Blog not found</h1>", status_code=404)
    
    # Delete related blog draft if it exists
    draft = db.query(BlogDraft).filter(BlogDraft.blog_id == blog_id).first()
    if draft:
        db.delete(draft)
    
    db.delete(blog)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.get("/blog/{blog_id}/refresh")
def refresh_blog_fragment(blog_id: str, db: Session = Depends(get_db)):
    """Return status and current processing step for auto-refresh / polling."""
    blog = db.query(Blog).filter(Blog.blog_id == blog_id).first()
    if not blog:
        return {"status": "NOT_FOUND"}
    step_label = BLOG_PROCESSING_STEP_LABELS.get(blog.processing_step, "Processing") if blog.processing_step else None
    return {
        "status": blog.status,
        "processing_step": blog.processing_step,
        "processing_step_label": step_label,
        "error_reason": blog.error_reason,
    }


# Channel Sources CRUD
@router.get("/sources/channels", response_class=HTMLResponse)
def channel_sources(request: Request, db: Session = Depends(get_db)):
    sources = db.query(ChannelSource).order_by(ChannelSource.created_at.desc()).all()
    return templates.TemplateResponse(
        "channel_sources.html",
        {
            "request": request,
            "sources": sources,
        },
    )


@router.post("/sources/channels")
def create_channel_source(url: str = Form(...), name: str = Form(None), db: Session = Depends(get_db)):
    # Check if URL already exists
    existing = db.query(ChannelSource).filter(ChannelSource.url == url.strip()).first()
    if existing:
        # Redirect with a simple error indicator (you could enhance this with flash messages)
        return RedirectResponse(url="/sources/channels?error=duplicate", status_code=303)
    
    source = ChannelSource(url=url.strip(), name=name.strip() if name else None)
    db.add(source)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        # Handle other potential errors
        return RedirectResponse(url="/sources/channels?error=failed", status_code=303)
    return RedirectResponse(url="/sources/channels?success=created", status_code=303)


@router.post("/sources/channels/{source_id}/toggle")
def toggle_channel_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(ChannelSource).filter(ChannelSource.id == source_id).first()
    if source:
        source.is_active = not source.is_active
        db.commit()
    return RedirectResponse(url="/sources/channels", status_code=303)


@router.post("/sources/channels/{source_id}/delete")
def delete_channel_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(ChannelSource).filter(ChannelSource.id == source_id).first()
    if source:
        db.delete(source)
        db.commit()
    return RedirectResponse(url="/sources/channels", status_code=303)


# Blog Sources CRUD
@router.get("/sources/blogs", response_class=HTMLResponse)
def blog_sources(request: Request, db: Session = Depends(get_db)):
    sources = db.query(BlogSource).order_by(BlogSource.created_at.desc()).all()
    return templates.TemplateResponse(
        "blog_sources.html",
        {
            "request": request,
            "sources": sources,
        },
    )


@router.post("/sources/blogs")
def create_blog_source(url: str = Form(...), name: str = Form(None), db: Session = Depends(get_db)):
    # Check if URL already exists
    existing = db.query(BlogSource).filter(BlogSource.url == url.strip()).first()
    if existing:
        # Redirect with a simple error indicator
        return RedirectResponse(url="/sources/blogs?error=duplicate", status_code=303)
    
    source = BlogSource(url=url.strip(), name=name.strip() if name else None)
    db.add(source)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        # Handle other potential errors
        return RedirectResponse(url="/sources/blogs?error=failed", status_code=303)
    return RedirectResponse(url="/sources/blogs?success=created", status_code=303)


@router.post("/sources/blogs/{source_id}/toggle")
def toggle_blog_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(BlogSource).filter(BlogSource.id == source_id).first()
    if source:
        source.is_active = not source.is_active
        db.commit()
    return RedirectResponse(url="/sources/blogs", status_code=303)


@router.post("/sources/blogs/{source_id}/delete")
def delete_blog_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(BlogSource).filter(BlogSource.id == source_id).first()
    if source:
        db.delete(source)
        db.commit()
    return RedirectResponse(url="/sources/blogs", status_code=303)


# Bulk delete endpoints
@router.post("/bulk-delete/videos")
def bulk_delete_videos(request: BulkDeleteVideos, db: Session = Depends(get_db)):
    deleted_count = 0
    for video_id in request.video_ids:
        video = db.query(Video).filter(Video.video_id == video_id).first()
        if video:
            # Delete related transcript and draft if they exist
            transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
            if transcript:
                db.delete(transcript)
            
            draft = db.query(Draft).filter(Draft.video_id == video_id).first()
            if draft:
                db.delete(draft)
            
            db.delete(video)
            deleted_count += 1
    
    db.commit()
    return {"deleted_count": deleted_count}


@router.post("/bulk-delete/blogs")
def bulk_delete_blogs(request: BulkDeleteBlogs, db: Session = Depends(get_db)):
    deleted_count = 0
    for blog_id in request.blog_ids:
        blog = db.query(Blog).filter(Blog.blog_id == blog_id).first()
        if blog:
            # Delete related blog draft if it exists
            draft = db.query(BlogDraft).filter(BlogDraft.blog_id == blog_id).first()
            if draft:
                db.delete(draft)
            
            db.delete(blog)
            deleted_count += 1
    
    db.commit()
    return {"deleted_count": deleted_count}
