# Content Generator MVP

Web app that (1) checks a list of YouTube channels daily for new uploads and stores them with status **NEW**, and (2) lets you pick a video, click **Generate Post**, and get a transcript + LinkedIn post draft. You copy the draft to LinkedIn manually.

## Prerequisites

- **Python 3.11+**
- **ffmpeg** – audio conversion and chunking (yt-dlp also uses it for postprocessing)  
  - macOS: `brew install ffmpeg`  
  - If the app can’t find ffmpeg (e.g. when run from an IDE), set `FFMPEG_LOCATION` in `.env` to the directory containing `ffmpeg` and `ffprobe` (e.g. `/opt/homebrew/bin` or `/usr/local/bin`).
- **yt-dlp** – audio-only download from YouTube  
  - Install: `pip install "yt-dlp[default]"` (recommended; includes EJS scripts for YouTube) or `pip install yt-dlp`  
  - Or system: `brew install yt-dlp`
- **A JavaScript runtime for YouTube** – yt-dlp needs one to extract from YouTube:
  - **Node.js** (v20+) – [nodejs.org](https://nodejs.org) or `brew install node`  
  - Or **Deno** (v2+) – [deno.com](https://deno.com)  
  Set `YT_DLP_JS_RUNTIMES=node` in `.env` if you use Node (default in this app), or `YT_DLP_JS_RUNTIMES=deno` for Deno.

## Setup

1. **Clone or unpack** the project and go to its directory:
   ```bash
   cd content-generator-app
   ```

2. **Create a virtualenv and install dependencies:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and set OPENAI_API_KEY=sk-...
   ```

4. **Add YouTube channels**  
   Edit `channels.txt` and add one YouTube channel URL per line, e.g.:
   - `https://www.youtube.com/@Fireship`
   - `https://www.youtube.com/channel/UCxxxxxxxxxx`

5. **Optional – writing style for LinkedIn**  
   Edit `style.md` with your tone and structure rules. This is used when generating the draft.

## How to run the server

```bash
python -m app.run_server
```

Then open **http://127.0.0.1:8000** in a browser.

## How to run the ingest job

From the project root with the same venv active:

```bash
python -m app.ingest_daily
```

This reads `channels.txt`, fetches each channel’s RSS feed, and inserts **new** videos (by `video_id`) with status **NEW**. Safe to run multiple times (idempotent).

## Scheduling daily ingest (cron)

Example crontab (run at 8:00 every day; adjust path and venv):

```cron
0 8 * * * cd /path/to/content-generator-app && .venv/bin/python -m app.ingest_daily
```

## How to use the UI

1. **Dashboard**  
   Videos are grouped by status: **NEW**, **PROCESSING**, **READY**, **MANUAL_REVIEW**, **POSTED**, **SKIPPED**.

2. **Generate Post**  
   For a **NEW** or **MANUAL_REVIEW** video, click **Generate Post** (or **Retry Generate**).  
   The app will:
   - Download audio (yt-dlp)
   - Convert to mono 16 kHz (ffmpeg)
   - Chunk long audio
   - Transcribe with OpenAI
   - Generate a LinkedIn draft from the transcript + `style.md`  
   The page shows **PROCESSING** and auto-refreshes every 5 seconds until it’s **READY** or **MANUAL_REVIEW**.

3. **Video detail**  
   Open a video to see:
   - Transcript (collapsible), **Copy Transcript**
   - LinkedIn draft, **Copy Draft**
   - **Open on YouTube**
   - **Mark POSTED** / **Mark SKIPPED**
   - **Retry Generate** if it’s in **MANUAL_REVIEW**

4. **Copy and paste**  
   Use **Copy Draft** (or **Copy Transcript**), then paste into LinkedIn.

## Optional: seed sample data

```bash
python -m app.dev_seed
```

Creates two sample videos (one NEW, one READY with transcript and draft) for local testing.

## Configuration (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | (required) |
| `OPENAI_TRANSCRIBE_MODEL` | Model for audio transcription | `gpt-4o-mini-transcribe` |
| `OPENAI_DRAFT_MODEL` | Model for LinkedIn draft | `gpt-4o-mini` |
| `DRAFT_MAX_CHARS` | Max characters in draft | `1200` |
| `AUDIO_CHUNK_MINUTES` | Chunk length for long audio (minutes) | `10` |
| `TIMEZONE` | Timezone for display | `America/Los_Angeles` |
| `YT_DLP_JS_RUNTIMES` | JS runtime for yt-dlp (YouTube): `node`, `deno`, `bun`, or `quickjs` | `node` |
| `FFMPEG_LOCATION` | Directory (or path to ffmpeg) for yt-dlp postprocessing. Empty = use PATH | (auto) |

## Tests

```bash
pytest tests/ -v
```

- `tests/test_ingest.py` – ingest dedupes by `video_id`.
- `tests/test_generate.py` – generate pipeline sets **MANUAL_REVIEW** and error when download or transcription fails (mocked external calls).

## Project layout

```
app/
  __init__.py
  config.py
  db.py
  models.py
  ingest.py
  generate.py
  audio.py
  routes.py
  main.py
  run_server.py
  ingest_daily.py
  dev_seed.py
  templates/
  static/
tests/
README.md
channels.txt
style.md
.env.example
requirements.txt
```

Data (DB, audio, chunks) is written under `./data/` (created automatically).
