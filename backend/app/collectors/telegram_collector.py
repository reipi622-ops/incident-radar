import os, asyncio
from typing import List
from loguru import logger
from app.collectors.base import BaseCollector, RawItem


def _lang(t):
    ar = sum(1 for c in t if '\u0600' <= c <= '\u06ff')
    he = sum(1 for c in t if '\u0590' <= c <= '\u05ff')
    return "ar" if ar > he and ar > 5 else "he" if he > ar and he > 5 else "en"


class TelegramChannelCollector(BaseCollector):
    def __init__(self, channel, api_id, api_hash, limit=50, session="/tmp/tg"):
        self._ch = channel.lstrip("@")
        self._id = api_id
        self._hash = api_hash
        self._limit = limit
        self._session = session

    @property
    def source_name(self):
        return f"telegram:{self._ch}"

    def collect(self):
        try:
            return asyncio.run(self._run())
        except Exception as e:
            logger.error(f"TG:{self._ch} {e}")
            return []

    async def _run(self):
        try:
            from telethon import TelegramClient
        except Exception:
            logger.error("pip install telethon")
            return []

        from telethon.sessions import StringSession
        from datetime import timezone

        items = []
        session = StringSession(os.environ.get('TG_SESSION', self._session))
        async with TelegramClient(session, self._id, self._hash) as c:
            try:
                e = await c.get_entity(self._ch)
            except Exception as ex:
                logger.error(f"TG entity {ex}")
                return []
            async for m in c.iter_messages(e, limit=self._limit):
                if not m.text:
                    continue
                ts = m.date
                if ts and ts.tzinfo:
                    ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
                items.append(RawItem(
                    external_id=f"{self._ch}_{m.id}",
                    source_name=self.source_name,
                    source_url=f"https://t.me/{self._ch}/{m.id}",
                    raw_text=m.text,
                    raw_timestamp=ts,
                    media_items=[],
                    language=_lang(m.text)
                ))
        return items


def build_telegram_collectors():
    aid = os.getenv("TELEGRAM_API_ID", "")
    ah = os.getenv("TELEGRAM_API_HASH", "")
    chs = os.getenv("TELEGRAM_CHANNELS", "")
    if not aid or not ah or not chs:
        return []
    return [TelegramChannelCollector(c.strip(), int(aid), ah) for c in chs.split(",") if c.strip()]
