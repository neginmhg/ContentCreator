"""Generate-post pipeline for blogs: fetch content -> create draft."""
from pathlib import Path

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import (
    OPENAI_API_KEY,
    OPENAI_DRAFT_MODEL,
    DRAFT_MAX_CHARS,
    STYLE_FILE,
)
from app.models import (
    Blog,
    BlogDraft,
    BLOG_STATUS_PROCESSING,
    BLOG_STATUS_READY,
    BLOG_STATUS_MANUAL_REVIEW,
    BLOG_PROCESSING_STEP_FETCH,
    BLOG_PROCESSING_STEP_DRAFT,
)


def _generate_draft(
    content: str,
    title: str,
    source_name: str,
    style_rules: str,
    model: str,
    max_chars: int,
) -> tuple[str | None, str | None]:
    """Generate LinkedIn draft from blog content + style. Returns (draft_text, error)."""
    if not OPENAI_API_KEY:
        return None, "OPENAI_API_KEY not set"
    client = OpenAI(api_key=OPENAI_API_KEY)
    system = f"""You write LinkedIn post drafts based only on the provided blog content and metadata. Do not invent or hallucinate any facts.

Rules:
- Max {max_chars} characters total.
- Structure: Hook (1–2 lines) -> 3–5 hyphen bullet takeaways -> one short opinion/insight -> CTA question at end -> 3–5 hashtags at end.
- Mention the source name and article title briefly.
- Use only information present in the blog content. If the content is short or unclear, write a safe post like "High-level takeaways from [title] by [source]:" and generic engagement hooks; never invent details.

User writing style rules:
{style_rules}
"""

    user = f"""Article title: {title}
Source: {source_name}

Content:
{content[:120000]}

Write one LinkedIn post draft that follows the rules and style above. Output only the post text, no preamble."""

    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=800,
        )
        text = (r.choices[0].message.content or "").strip()
        if len(text) > max_chars:
            text = text[: max_chars - 3] + "..."
        return text or None, None
    except Exception as e:
        return None, str(e)[:500]


def run_blog_generate_pipeline(db: Session, blog_id: str) -> None:
    """
    Full pipeline for one blog: set PROCESSING -> fetch content -> generate draft -> save draft -> set READY.
    On any failure: set MANUAL_REVIEW and store error.
    On retry, resumes from the last failed step.
    """
    blog = db.query(Blog).filter(Blog.blog_id == blog_id).first()
    if not blog:
        return
    
    # Determine if this is a retry and where to start
    is_retry = blog.status == BLOG_STATUS_MANUAL_REVIEW and blog.processing_step
    
    # Determine which step to start from
    start_step = None
    if is_retry:
        # Start from the step after the last completed step, or from the failed step if no completed step
        if blog.last_completed_step:
            step_order = [BLOG_PROCESSING_STEP_FETCH, BLOG_PROCESSING_STEP_DRAFT]
            if blog.last_completed_step in step_order:
                current_index = step_order.index(blog.last_completed_step)
                if current_index + 1 < len(step_order):
                    start_step = step_order[current_index + 1]
        else:
            start_step = blog.processing_step
    
    blog.status = BLOG_STATUS_PROCESSING
    blog.error_reason = None
    db.commit()

    # Ensure blog draft row exists (upsert)
    draft = db.query(BlogDraft).filter(BlogDraft.blog_id == blog_id).first()
    if not draft:
        draft = BlogDraft(blog_id=blog_id, text="")
        db.add(draft)
        db.commit()

    def fail(msg: str) -> None:
        blog.status = BLOG_STATUS_MANUAL_REVIEW
        blog.processing_step = None
        blog.error_reason = msg
        db.commit()

    def complete_step(step: str) -> None:
        blog.last_completed_step = step
        db.commit()

    # Check if we need to fetch content (skip if already exists and we're retrying after fetch)
    need_fetch = not is_retry or start_step in (None, BLOG_PROCESSING_STEP_FETCH)
    
    if need_fetch:
        # 1) Fetch content (already done during ingestion, but we can re-fetch if needed)
        blog.processing_step = BLOG_PROCESSING_STEP_FETCH
        db.commit()
        
        # Content should already be available from ingestion
        if not blog.content:
            fail("No content available for this blog post")
            return
            
        complete_step(BLOG_PROCESSING_STEP_FETCH)

    # Check if we need to generate draft (skip if already generated and we're retrying after draft)
    need_draft = not is_retry or start_step in (None, BLOG_PROCESSING_STEP_FETCH, BLOG_PROCESSING_STEP_DRAFT)
    
    if need_draft:
        # 2) Draft
        blog.processing_step = BLOG_PROCESSING_STEP_DRAFT
        db.commit()
        style_rules = ""
        if STYLE_FILE.exists():
            style_rules = STYLE_FILE.read_text(encoding="utf-8", errors="replace")
        draft_text, err = _generate_draft(
            content=blog.content or "",
            title=blog.title,
            source_name=blog.source_name,
            style_rules=style_rules,
            model=OPENAI_DRAFT_MODEL,
            max_chars=DRAFT_MAX_CHARS,
        )
        if err:
            fail(f"Draft: {err}")
            return

        # 3) Save draft and set READY
        draft.text = draft_text or ""
        complete_step(BLOG_PROCESSING_STEP_DRAFT)

    # Final success state
    blog.status = BLOG_STATUS_READY
    blog.processing_step = None
    blog.error_reason = None
    db.commit()
