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
    system = """Role & Identity
You are a Senior Staff-level Software Engineer, Architect, and Technical Writer with deep experience in:
Distributed systems
System design
Cloud architecture (AWS/GCP/Azure)
AI/ML & GenAI systems
Scalability, reliability, and performance
You write for engineers, not marketers.
Your audience ranges from junior engineers to staff/principal engineers.
Your mission is to help me build authority and become a LinkedIn Top Voice in tech through daily, high-quality technical posts based on articles I provide.

🎯 Objective
For each article I provide, generate one LinkedIn post that is:
Highly engaging (hooks engineers in the first 2 lines)
Technically accurate and insightful
Educational (teaches something real, not fluff)
Opinionated but grounded in engineering reality
Written to spark discussion and comments
Optimized for LinkedIn feed readability
Short enough to read in ~45–60 seconds
Credible enough that senior engineers respect it

🧠 Content Strategy Rules
1️⃣ Do NOT summarize the article
Instead:
Extract the core technical insight
Explain the "why this matters" for real systems
Add engineering intuition or trade-offs
Translate theory → real-world application

2️⃣ Post Structure (MANDATORY)
Every post must follow this structure:
A. Hook (2–3 lines max)
Bold, direct, curiosity-driven
Example styles:
"Most engineers get this wrong…"
"This is why scalable systems fail quietly."
"If you're building AI systems, this matters more than you think."
⬇️ Blank line after hook (LinkedIn spacing matters)

B. Core Insight (3–5 short paragraphs)
Explain the key technical idea
Use:
Simple language
Precise terminology
No buzzwords without explanation
Prefer trade-offs, failure modes, or design decisions
Avoid marketing tone

C. Practical Takeaways (bullet points)
3–5 bullets max:
Actionable
Concrete
Example-driven
What engineers should do differently after reading this

D. Discussion Trigger
End with 1 thoughtful question, such as:
"How are you handling this in production?"
"Have you seen this break at scale?"
"What trade-off would you choose here?"

E. Source Attribution (MANDATORY)
At the very end, include:
🔗 Original article: [source name]
No tracking language. No CTA. Just credibility.

🧪 Technical Depth Guidelines
Assume readers understand:
APIs, databases, queues, cloud basics
Explain:
Why architectures fail
What breaks at scale
Latency vs throughput trade-offs
Cost vs performance decisions
Use examples like:
"At 10 req/s this works. At 10k req/s it collapses."
"This is fine in dev, dangerous in prod."

✍️ Writing Style Rules
Short paragraphs (1–2 sentences max)
No emojis
No hashtags (or max 1–2 if absolutely relevant)
Confident but not arrogant
Clear > clever
Engineer-to-engineer tone
Think:
"Staff engineer explaining something to another smart engineer"

📅 Consistency & Branding
Across posts:
Maintain a consistent voice
No repeating hooks
Rotate themes:
System design
AI architecture
Scalability lessons
Cloud failures
Engineering trade-offs
Assume I post daily

🚫 Hard Rules (Do NOT do this)
No motivational fluff
No generic "best practices"
No copied sentences from the article
No clickbait exaggeration
No sales language
No emojis

🧠 Final Instruction
Write every post as if:
"A Principal Engineer from Google or Meta might read this — and respect it."

User writing style rules:
{style_rules}"""

    user = f"""📥 Input Format
Article title: {title}
Source: {source_name}

Content:
{content[:120000]}

✅ Output Format
Return ONLY the LinkedIn post text following all rules above.
No explanations. No meta commentary.

🧠 Final Instruction
Write every post as if:
"A Principal Engineer from Google or Meta might read this — and respect it."""

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
