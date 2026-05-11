import os
from typing import List
from datetime import datetime, timezone
from loguru import logger

from app.collectors.base import BaseCollector, RawItem


def _lang(s):
    ar = sum(1 for c in s if '\u0600' <= c <= '\u06FF')
    he = sum(1 for c in s if '\u05D0' <= c <= '\u05EA')
    return "ar" if ar > he else "he"


def _get_string_session() -> str:
    """Return a Telethon StringSession string from env vars.

    Supports two env var layouts:
      TELEGRAM_STRING_SESSION=<full session>          (preferred)
      TELEGRAM_SESSION_1=<first half>                 (legacy split for Railway's 512-char limit)
      TELEGRAM_SESSION_2=<second half>
    """
    s = os.getenv("TELEGRAM_STRING_SESSION", "").strip()
    if s:
        return s
    part1 = os.getenv("TELEGRAM_SESSION_1", "").strip()
    part2 = os.getenv("TELEGRAM_SESSION_2", "").strip()
    return part1 + part2


class TelegramChannelCollector(BaseCollector):
    def __init__(self, channel, api_id, api_hash, string_session: str = "", limit=50):
        self._ch = channel
        self.api_id = int(api_id)
        self.api_hash = api_hash
        self._string_session = string_session
        self._limit = limit

    @property
    def source_name(self):
        return f"Telegram({self._ch})"

    async def collect(self) -> List[RawItem]:
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            from telethon.tl.types import Message
        except ImportError:
            logger.error("pip install telethon")
            return []

        if not self._string_session:
            logger.error(f"TG({self._ch}) no session string \u2014 set TELEGRAM_STRING_SESSION")
            return []

        items = []
        try:
            async with TelegramClient(
                StringSession(self._string_session), self.api_id, self.api_hash
            ) as c:
                async for m in c.iter_messages(self._ch, limit=self._limit):
                    try:
                        if not isinstance(m, Message):
                            continue
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
                        logger.error(f"TG({self._ch}) message skip: {e}")
                        continue
        except Exception as e:
            logger.error(f"TG({self._ch}) collect error: {e}")

        return items


def build_telegram_collectors() -> List[TelegramChannelCollector]:
    api_id = os.getenv("TELEGRAM_API_ID", "")
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    string_session = _get_string_session()
    raw = os.getenv("TELEGRAM_CHANNELS", "").replace(";", ",").replace("\n", ",").replace("\r", ",")
    channels = [c.strip().lstrip("@") for c in raw.split(",") if c.strip()]
    if not api_id or not api_hash or not channels:
        logger.warning("Telegram not configured — set TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_CHANNELS")
        return []
    if not string_session:
        logger.warning("Telegram session missing — set TELEGRAM_STRING_SESSION (or TELEGRAM_SESSION_1/2)")
        return []
    logger.info(f"Building collectors for {len(channels)} channels: {channels}")
    return [TelegramChannelCollector(ch, api_id, api_hash, string_session) for ch in channels]
