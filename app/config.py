"""Load configuration from environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Paths (relative to project root when run from project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHANNELS_FILE = PROJECT_ROOT / "channels.txt"
BLOGS_FILE = PROJECT_ROOT / "blogs.txt"
STYLE_FILE = PROJECT_ROOT / "style.md"

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL:
    # Production database (PostgreSQL, etc.)
    DB_URL = DATABASE_URL
    IS_PRODUCTION = True
else:
    # Development database (SQLite)
    IS_PRODUCTION = False
    DB_PATH = PROJECT_ROOT / "data" / "content.db"
    DB_URL = f"sqlite:///{DB_PATH}"

# Only create local directories if not in production
if not IS_PRODUCTION:
    DATA_DIR = PROJECT_ROOT / "data"
    AUDIO_DIR = DATA_DIR / "audio"
    CHUNKS_DIR = DATA_DIR / "chunks"
    DB_PATH = DATA_DIR / "content.db"
    
    # Ensure dirs exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
else:
    # Production paths (for reference, though audio may need temp storage)
    DATA_DIR = Path("/tmp/content_generator_data")
    AUDIO_DIR = DATA_DIR / "audio"
    CHUNKS_DIR = DATA_DIR / "chunks"

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
OPENAI_DRAFT_MODEL = os.getenv("OPENAI_DRAFT_MODEL", "gpt-4o-mini")
DRAFT_MAX_CHARS = int(os.getenv("DRAFT_MAX_CHARS", "1200"))
AUDIO_CHUNK_MINUTES = int(os.getenv("AUDIO_CHUNK_MINUTES", "10"))
TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")

# yt-dlp: YouTube requires a JS runtime. Set to "node", "deno", "bun", or "quickjs" (must be installed).
# Use "node" if you have Node.js; leave empty to let yt-dlp use its default (Deno).
YT_DLP_JS_RUNTIMES = os.getenv("YT_DLP_JS_RUNTIMES", "node").strip() or None

# ffmpeg: Path to ffmpeg binary or directory containing ffmpeg/ffprobe. Leave empty to auto-detect from PATH.
FFMPEG_LOCATION = os.getenv("FFMPEG_LOCATION", "").strip() or None
