"""Audio download (yt-dlp), conversion (ffmpeg), and chunking."""
import shutil
import subprocess
from pathlib import Path

from app.config import (
    AUDIO_DIR,
    CHUNKS_DIR,
    AUDIO_CHUNK_MINUTES,
    YT_DLP_JS_RUNTIMES,
    FFMPEG_LOCATION,
)


def _ffmpeg_location_for_ytdlp() -> str | None:
    """Return path to ffmpeg or its directory for yt-dlp --ffmpeg-location."""
    if FFMPEG_LOCATION:
        p = Path(FFMPEG_LOCATION).resolve()
        if p.is_file():
            return str(p.parent)
        if p.is_dir():
            return str(p)
        return FFMPEG_LOCATION
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return str(Path(ffmpeg).parent)
    return None


def download_audio(video_id: str, video_url: str) -> tuple[Path | None, str | None]:
    """
    Download best-audio only with yt-dlp. Save to data/audio/<video_id>.<ext>.
    Returns (path, None) on success or (None, error_message) on failure.
    YouTube requires a JS runtime (Node, Deno, etc.); set YT_DLP_JS_RUNTIMES in .env if needed.
    """
    out_tmpl = str(AUDIO_DIR / f"{video_id}.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bestaudio/best",
        "-x",
        "--no-playlist",
        "-o", out_tmpl,
        "--no-overwrites",
    ]
    ffmpeg_loc = _ffmpeg_location_for_ytdlp()
    if ffmpeg_loc:
        cmd.extend(["--ffmpeg-location", ffmpeg_loc])
    else:
        return None, (
            "ffmpeg/ffprobe not found. Install ffmpeg (e.g. brew install ffmpeg) and ensure it is on PATH, "
            "or set FFMPEG_LOCATION in .env to the path to ffmpeg or its directory."
        )
    # YouTube needs a JS runtime. Prefer explicit runtime so extraction works (e.g. node or deno).
    if YT_DLP_JS_RUNTIMES:
        cmd.extend(["--js-runtimes", YT_DLP_JS_RUNTIMES])
    # Allow yt-dlp to fetch EJS scripts from GitHub when using pip-installed yt-dlp
    cmd.append("--remote-components")
    cmd.append("ejs:github")
    cmd.append(video_url)
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return None, "yt-dlp timed out after 10 minutes"
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or str(e))[:500]
        return None, f"yt-dlp failed: {err}"
    except FileNotFoundError:
        return None, "yt-dlp not found; install with: pip install yt-dlp (or brew install yt-dlp)"

    # Find the file we wrote (ext can be m4a, webm, etc.)
    for p in AUDIO_DIR.glob(f"{video_id}.*"):
        if p.suffix.lower() in (".m4a", ".webm", ".opus", ".mp3", ".wav"):
            return p, None
    return None, "yt-dlp did not produce a known audio file"


def convert_to_wav_16k_mono(source: Path, dest: Path) -> tuple[bool, str | None]:
    """
    Convert source audio to mono 16kHz WAV for transcription.
    Returns (True, None) on success or (False, error_message).
    """
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", str(source),
                "-acodec", "pcm_s16le",
                "-ac", "1",
                "-ar", "16000",
                str(dest),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return True, None
    except subprocess.TimeoutExpired:
        return False, "ffmpeg conversion timed out"
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or str(e))[-500:]
        return False, f"ffmpeg failed: {err}"
    except FileNotFoundError:
        return False, "ffmpeg not found; install with: brew install ffmpeg"


def chunk_audio(wav_path: Path, video_id: str, chunk_minutes: int | None = None) -> tuple[list[Path], str | None]:
    """
    Split WAV into chunks of chunk_minutes (default from config).
    Writes to data/chunks/<video_id>/0.wav, 1.wav, ...
    Returns (list of paths, None) or ([], error_message).
    """
    chunk_minutes = chunk_minutes or AUDIO_CHUNK_MINUTES
    duration_sec = chunk_minutes * 60
    out_dir = CHUNKS_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Get duration with ffprobe
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(wav_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            return [], f"ffprobe failed: {r.stderr or r.stdout}"
        total = float(r.stdout.strip())
    except Exception as e:
        return [], f"ffprobe error: {e}"

    paths = []
    start = 0.0
    i = 0
    while start < total:
        out_path = out_dir / f"{i}.wav"
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i", str(wav_path),
                    "-ss", str(start),
                    "-t", str(duration_sec),
                    "-acodec", "copy",
                    str(out_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.CalledProcessError as e:
            return paths, f"ffmpeg chunk failed: {e.stderr or e.stdout}"
        if out_path.exists() and out_path.stat().st_size > 0:
            paths.append(out_path)
        start += duration_sec
        i += 1
    return paths, None
