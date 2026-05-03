"""
Seed script — loads sample_data/mock_reports.json into the database.
Run: python -m scripts.seed_db
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal
from app.collectors.local_json import LocalJsonCollector
from app.collectors.service import run_collector


def main():
    sample_path = Path(__file__).parent.parent.parent / "sample_data" / "mock_reports.json"
    if not sample_path.exists():
        print(f"ERROR: sample data not found at {sample_path}")
        sys.exit(1)

    db = SessionLocal()
    try:
        collector = LocalJsonCollector(file_path=sample_path, source_name="mock_seed")
        result = run_collector(collector, db)
        print(f"Seed complete: {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
