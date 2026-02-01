"""Tests for generate pipeline (status transitions, error handling) with mocked externals."""
from unittest.mock import patch, MagicMock

from app.models import Video, VIDEO_STATUS_NEW, VIDEO_STATUS_MANUAL_REVIEW
from app.generate import run_generate_pipeline


def test_generate_pipeline_sets_manual_review_on_download_failure(db_session):
    """When audio download fails, video stays in DB and status becomes MANUAL_REVIEW with error."""
    db_session.add(Video(
        video_id="err_video_1",
        title="Test",
        url="https://www.youtube.com/watch?v=err_video_1",
        channel_name="Channel",
        status=VIDEO_STATUS_NEW,
    ))
    db_session.commit()

    with patch("app.generate.download_audio") as mock_dl:
        mock_dl.return_value = (None, "yt-dlp failed: simulated error")
        run_generate_pipeline(db_session, "err_video_1")

    db_session.expire_all()  # reload from DB
    video = db_session.query(Video).filter(Video.video_id == "err_video_1").first()
    assert video is not None
    assert video.status == VIDEO_STATUS_MANUAL_REVIEW
    assert "simulated error" in (video.error_reason or "")


def test_generate_pipeline_sets_manual_review_on_transcribe_failure(db_session):
    """When transcription fails, video becomes MANUAL_REVIEW and transcript stores error."""
    db_session.add(Video(
        video_id="err_video_2",
        title="Test",
        url="https://www.youtube.com/watch?v=err_video_2",
        channel_name="Channel",
        status=VIDEO_STATUS_NEW,
    ))
    db_session.commit()

    with patch("app.generate.download_audio", return_value=(MagicMock(), None)), \
         patch("app.generate.convert_to_wav_16k_mono", return_value=(True, None)), \
         patch("app.generate.chunk_audio", return_value=([MagicMock()], None)), \
         patch("app.generate._run_transcription", return_value=(None, None, "OpenAI rate limit")):
        run_generate_pipeline(db_session, "err_video_2")

    db_session.expire_all()
    video = db_session.query(Video).filter(Video.video_id == "err_video_2").first()
    assert video is not None
    assert video.status == VIDEO_STATUS_MANUAL_REVIEW
    assert "rate limit" in (video.error_reason or "").lower() or "OpenAI" in (video.error_reason or "")
