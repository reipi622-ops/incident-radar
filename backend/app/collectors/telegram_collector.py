import os
from typing import List
from datetime import datetime, timezone
from loguru import logger

from app.collectors.base import BaseCollector, RawItem


def _lang(s):
    ar = sum(1 for c in s if '\u0600' <= c <= '\u06FF')
    he = sum(1 for c in s if '\u05D0' <= c <= '\u05EA')
    return "ar" if ar > he else "he"


class TelegramChannelCollector(BaseCollector):
    def __init__(self, channel, api_id, api_hash, limit=50, session="tmp/tg"):
        self._ch = channel
        self.api_id = int(api_id)
        self.api_hash = api_hash
        self._limit = limit
        self._session = session

    @property
    def source_name(self):
        return f"Telegram({self._ch})"

    async def collect(self) -> List[RawItem]:
        try:
            from telethon import TelegramClient
        except ImportError:
            logger.error("pip install telethon")
            return []

        items = []
        try:
            async with TelegramClient(self._session, self.api_id, self.api_hash) as c:
                async for m in c.iter_messages(self._ch, limit=self._limit):
                    try:
                        if not m.text:
                            continue
                        ts = m.date.replace(tzinfo=timezone.utc)
                        items.append(RawItem(
                            external_id=f"{self._ch}/{m.id}",
                            source_name=self.source_name,
                            source_url=f"https://t.me/{self._ch}/{m.id}",
                            raw_text=m.text,
                            raw_timestamp=ts,
                            media_items=[],
                            language=_lang(m.text),
                        ))
                    except Exception as e:
                        logger.error(f"TG entity {e}")
                        continue
        except Exception as e:
            logger.error(f"TG({self._ch}) {e}")

        return items


def build_telegram_collectors() -> List[TelegramChannelCollector]:
    api_id = os.getenv("TELEGRAM_API_ID", "")
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    channels = [c.strip() for c in os.getenv("TELEGRAM_CHANNELS", "").split(",") if c.strip()]
    return [TelegramChannelCollector(ch, api_id, api_hash) for ch in channels]
