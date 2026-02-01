"""Generate-post pipeline: download audio -> transcribe -> create draft."""
from pathlib import Path

from openai import OpenAI
from sqlalchemy.orm import Session

from app.audio import download_audio, convert_to_wav_16k_mono, chunk_audio
from app.config import (
    OPENAI_API_KEY,
    OPENAI_TRANSCRIBE_MODEL,
    OPENAI_DRAFT_MODEL,
    DRAFT_MAX_CHARS,
    STYLE_FILE,
    AUDIO_DIR,
    CHUNKS_DIR,
)
from app.models import (
    Video,
    Transcript,
    Draft,
    VIDEO_STATUS_PROCESSING,
    VIDEO_STATUS_READY,
    VIDEO_STATUS_MANUAL_REVIEW,
    PROCESSING_STEP_DOWNLOAD,
    PROCESSING_STEP_CONVERT,
    PROCESSING_STEP_CHUNK,
    PROCESSING_STEP_TRANSCRIBE,
    PROCESSING_STEP_DRAFT,
)


def _transcribe_chunk(client: OpenAI, path: Path, model: str) -> tuple[str | None, str | None]:
    """Transcribe one audio file. Returns (text, None) or (None, error)."""
    with open(path, "rb") as f:
        try:
            r = client.audio.transcriptions.create(model=model, file=f, response_format="text")
            return (r if isinstance(r, str) else getattr(r, "text", str(r))), None
        except Exception as e:
            return None, str(e)[:500]


def _run_transcription(video_id: str, chunk_paths: list[Path], model: str) -> tuple[str | None, str | None, str | None]:
    """
    Transcribe all chunks and merge in order.
    Returns (full_text, language_used, error). language_used may be None.
    """
    if not OPENAI_API_KEY:
        return None, None, "OPENAI_API_KEY not set"
    client = OpenAI(api_key=OPENAI_API_KEY)
    parts = []
    for p in chunk_paths:
        text, err = _transcribe_chunk(client, p, model)
        if err:
            return None, None, err
        if text and text.strip():
            parts.append(text.strip())
    full = "\n\n".join(parts) if parts else ""
    return full, None, None


def _generate_draft(
    transcript: str,
    title: str,
    channel_name: str,
    style_rules: str,
    model: str,
    max_chars: int,
) -> tuple[str | None, str | None]:
    """Generate LinkedIn draft from transcript + style. Returns (draft_text, error)."""
    if not OPENAI_API_KEY:
        return None, "OPENAI_API_KEY not set"
    client = OpenAI(api_key=OPENAI_API_KEY)
    system = f"""You write LinkedIn post drafts based only on the provided transcript and metadata. Do not invent or hallucinate any facts.

Rules:
- Max {max_chars} characters total.
- Structure: Hook (1–2 lines) -> 3–5 hyphen bullet takeaways -> one short opinion/insight -> CTA question at end -> 3–5 hashtags at end.
- Mention the channel/creator name and video title briefly.
- Use only information present in the transcript. If the transcript is short or unclear, write a safe post like "High-level takeaways from [title] by [channel]:" and generic engagement hooks; never invent details.

User writing style rules:
{style_rules}
"""

    user = f"""Video title: {title}
Channel: {channel_name}

Transcript:
{transcript[:120000]}

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


def run_generate_pipeline(db: Session, video_id: str) -> None:
    """
    Full pipeline for one video: set PROCESSING -> download -> convert -> chunk -> transcribe -> save transcript
    -> generate draft -> save draft -> set READY. On any failure: set MANUAL_REVIEW and store error.
    On retry, resumes from the last failed step.
    """
    video = db.query(Video).filter(Video.video_id == video_id).first()
    if not video:
        return
    
    # Determine if this is a retry and where to start
    is_retry = video.status == VIDEO_STATUS_MANUAL_REVIEW and video.processing_step
    
    # Determine which step to start from
    start_step = None
    if is_retry:
        # Start from the step after the last completed step, or from the failed step if no completed step
        if video.last_completed_step:
            step_order = [PROCESSING_STEP_DOWNLOAD, PROCESSING_STEP_CONVERT, PROCESSING_STEP_CHUNK, PROCESSING_STEP_TRANSCRIBE, PROCESSING_STEP_DRAFT]
            if video.last_completed_step in step_order:
                current_index = step_order.index(video.last_completed_step)
                if current_index + 1 < len(step_order):
                    start_step = step_order[current_index + 1]
        else:
            start_step = video.processing_step
    
    video.status = VIDEO_STATUS_PROCESSING
    video.error_reason = None
    db.commit()

    # Ensure transcript row exists (upsert)
    trans = db.query(Transcript).filter(Transcript.video_id == video_id).first()
    if not trans:
        trans = Transcript(video_id=video_id, status="PENDING")
        db.add(trans)
        db.commit()

    def fail(msg: str) -> None:
        video.status = VIDEO_STATUS_MANUAL_REVIEW
        video.processing_step = None
        video.error_reason = msg
        trans.status = "FAILED"
        trans.error = msg
        db.commit()

    def complete_step(step: str) -> None:
        video.last_completed_step = step
        db.commit()

    # Check if we need to download audio (skip if already exists and we're retrying after download)
    wav_path = AUDIO_DIR / f"{video_id}.wav"
    need_download = not is_retry or start_step in (None, PROCESSING_STEP_DOWNLOAD)
    
    if need_download:
        # 1) Download audio
        video.processing_step = PROCESSING_STEP_DOWNLOAD
        db.commit()
        path, err = download_audio(video_id, video.url)
        if err:
            fail(f"Download: {err}")
            return
        assert path is not None
        complete_step(PROCESSING_STEP_DOWNLOAD)

    # Check if we need to convert audio (skip if already converted and we're retrying after convert)
    need_convert = not is_retry or start_step in (None, PROCESSING_STEP_DOWNLOAD, PROCESSING_STEP_CONVERT)
    
    if need_convert:
        # 2) Convert to mono 16kHz WAV
        video.processing_step = PROCESSING_STEP_CONVERT
        db.commit()
        if not need_download:
            # If we skipped download, we need the original path
            # Try to find the downloaded file
            from app.audio import AUDIO_DIR
            original_extensions = ['.mp4', '.webm', '.mp3', '.m4a']
            path = None
            for ext in original_extensions:
                potential_path = AUDIO_DIR / f"{video_id}{ext}"
                if potential_path.exists():
                    path = potential_path
                    break
            if not path:
                fail("Original audio file not found for conversion")
                return
        
        ok, err = convert_to_wav_16k_mono(path, wav_path)
        if not ok or err:
            fail(f"Convert: {err or 'unknown'}")
            return
        complete_step(PROCESSING_STEP_CONVERT)

    # Check if we need to chunk audio (skip if already chunked and we're retrying after chunk)
    need_chunk = not is_retry or start_step in (None, PROCESSING_STEP_DOWNLOAD, PROCESSING_STEP_CONVERT, PROCESSING_STEP_CHUNK)
    
    if need_chunk:
        # 3) Chunk
        video.processing_step = PROCESSING_STEP_CHUNK
        db.commit()
        chunk_paths, err = chunk_audio(wav_path, video_id)
        if err and not chunk_paths:
            fail(f"Chunk: {err}")
            return
        if not chunk_paths:
            # Use full file as one chunk
            chunk_paths = [wav_path]
        complete_step(PROCESSING_STEP_CHUNK)

    # Check if we need to transcribe (skip if already transcribed and we're retrying after transcribe)
    need_transcribe = not is_retry or start_step in (None, PROCESSING_STEP_DOWNLOAD, PROCESSING_STEP_CONVERT, PROCESSING_STEP_CHUNK, PROCESSING_STEP_TRANSCRIBE)
    
    if need_transcribe:
        # 4) Transcribe
        video.processing_step = PROCESSING_STEP_TRANSCRIBE
        db.commit()
        full_text, lang, err = _run_transcription(video_id, chunk_paths, OPENAI_TRANSCRIBE_MODEL)
        if err:
            fail(f"Transcribe: {err}")
            return
        trans.text = full_text or ""
        trans.status = "OK"
        trans.model_used = OPENAI_TRANSCRIBE_MODEL
        trans.language = lang
        trans.word_count = len((full_text or "").split())
        trans.error = None
        db.commit()
        complete_step(PROCESSING_STEP_TRANSCRIBE)

    # Check if we need to generate draft (skip if already generated and we're retrying after draft)
    need_draft = not is_retry or start_step in (None, PROCESSING_STEP_DOWNLOAD, PROCESSING_STEP_CONVERT, PROCESSING_STEP_CHUNK, PROCESSING_STEP_TRANSCRIBE, PROCESSING_STEP_DRAFT)
    
    if need_draft:
        # 5) Draft
        video.processing_step = PROCESSING_STEP_DRAFT
        db.commit()
        style_rules = ""
        if STYLE_FILE.exists():
            style_rules = STYLE_FILE.read_text(encoding="utf-8", errors="replace")
        draft_text, err = _generate_draft(
            transcript=trans.text or "",
            title=video.title,
            channel_name=video.channel_name,
            style_rules=style_rules,
            model=OPENAI_DRAFT_MODEL,
            max_chars=DRAFT_MAX_CHARS,
        )
        if err:
            fail(f"Draft: {err}")
            return

        # 6) Save draft and set READY
        existing = db.query(Draft).filter(Draft.video_id == video_id).first()
        if existing:
            existing.text = draft_text or ""
        else:
            db.add(Draft(video_id=video_id, text=draft_text or ""))
        complete_step(PROCESSING_STEP_DRAFT)

    # Final success state
    video.status = VIDEO_STATUS_READY
    video.processing_step = None
    video.error_reason = None
    trans.error = None  # Clear any previous transcript errors
    db.commit()
