import json
from pathlib import Path
from datetime import datetime
from typing import List
from loguru import logger

from app.collectors.base import BaseCollector, RawItem


class LocalJsonCollector(BaseCollector):
    """
    Reads incident reports from a local JSON file.
    Used for development and testing without external dependencies.

    Expected JSON format: list of objects with keys:
      - id (str)
      - text (str)
      - timestamp (str ISO8601, optional)
      - url (str, optional)
      - media (list of {url, type}, optional)
      - language (str, optional)
    """

    def __init__(self, file_path: str | Path, source_name: str = "local_mock"):
        self._file_path = Path(file_path)
        self._source_name = source_name

    @property
    def source_name(self) -> str:
        return self._source_name

    def collect(self) -> List[RawItem]:
        if not self._file_path.exists():
            logger.warning(f"JSON file not found: {self._file_path}")
            return []

        try:
            raw = json.loads(self._file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {self._file_path}: {e}")
            return []

        items = []
        for entry in raw:
            try:
                timestamp = None
                if ts := entry.get("timestamp"):
                    try:
                        timestamp = datetime.fromisoformat(ts)
                    except ValueError:
                        logger.warning(f"Could not parse timestamp: {ts}")

                item = RawItem(
                    external_id=str(entry["id"]),
                    source_name=self._source_name,
                    source_url=entry.get("url"),
                    raw_text=entry["text"],
                    raw_timestamp=timestamp,
                    media_items=entry.get("media", []),
                    language=entry.get("language", "he"),
                )
                items.append(item)
            except KeyError as e:
                logger.warning(f"Skipping malformed entry (missing {e}): {entry.get('id', '?')}")

        logger.info(f"[{self.source_name}] Collected {len(items)} items from {self._file_path.name}")
        return items
