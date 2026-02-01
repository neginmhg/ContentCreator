"""CLI entrypoint for daily ingest."""
import sys
from pathlib import Path

# Run from project root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, init_db
from app.ingest import ingest_daily


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        inserted, errors = ingest_daily(db)
        print(f"Inserted {inserted} new video(s). Channel errors: {errors}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
