"""
Parsing Engine — Incident Radar
================================
Layer 1: Regex-based field extraction  (fast, deterministic, Hebrew-first)
Layer 2: Text normalization            (numbers, dates, locations)
Layer 3: Confidence scoring            (how reliable is each extracted field)
Layer 4: Structured ParsedReport output

Designed to be extended with NLP / LLM layers without breaking existing callers.
Arabic and English patterns are structurally present; populate as needed.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from loguru import logger

from app.models.enums import EventType


# ── Hebrew number words → int ─────────────────────────────────────────────────

_HE_NUM_WORDS: dict[str, int] = {
    "אחד": 1, "אחת": 1, "שניים": 2, "שתיים": 2, "שני": 2, "שתי": 2,
    "שלושה": 3, "שלוש": 3, "ארבעה": 4, "ארבע": 4, "חמישה": 5, "חמש": 5,
    "שישה": 6, "שש": 6, "שבעה": 7, "שבע": 7, "שמונה": 8,
    "תשעה": 9, "תשע": 9, "עשרה": 10, "עשר": 10,
    "אחד עשר": 11, "שנים עשר": 12, "עשרים": 20, "שלושים": 30,
    "ארבעים": 40, "חמישים": 50, "שישים": 60, "שבעים": 70,
    "מאה": 100, "מאות": 100,
}


def _parse_number(text: str) -> Optional[int]:
    """Convert digit string or Hebrew word to int."""
    text = text.strip()
    if text.isdigit():
        return int(text)
    return _HE_NUM_WORDS.get(text)


# ── Extraction patterns ───────────────────────────────────────────────────────

# Each list: try in order, return first match
_INJURED_RE = [
    re.compile(r'(\d+)\s*(?:פצוע(?:ים)?|נפגע(?:ים)?)', re.UNICODE),
    re.compile(r'(?:פצוע(?:ים)?|נפגע(?:ים)?)\s*[:\-]?\s*(\d+)', re.UNICODE),
    re.compile(r'(\d+)\s*(?:נפגעו|פצועים)', re.UNICODE),
]

_KILLED_RE = [
    re.compile(r'(\d+)\s*(?:הרוג(?:ים)?|נהרג(?:ו)?|מת(?:ים)?)', re.UNICODE),
    re.compile(r'(?:הרוג(?:ים)?|נהרג(?:ו)?)\s*[:\-]?\s*(\d+)', re.UNICODE),
    re.compile(r'נהרג(?:ו)?\s+(\d+)', re.UNICODE),
    re.compile(r'נמצא(?:ה)?\s+גופ', re.UNICODE),   # body found → 1 killed
]

# Location: after prepositions ב/ל + city/street indicators
_LOCATION_RE = [
    re.compile(
        r'ב(?:רחוב|שכונת|עיר|כפר|מושב|ישוב|אזור|אתר|כביש|צומת|שדה|בניין)\s+([\u0590-\u05ff\w\s\-״\'\"]{2,40})',
        re.UNICODE
    ),
    re.compile(
        r'(?:בתל אביב|בחיפה|בירושלים|בבאר שבע|בנתניה|בראשון לציון|בפתח תקווה|ברמת גן|בנהריה|ביפו)',
        re.UNICODE
    ),
    re.compile(r'(?:תל אביב|חיפה|ירושלים|באר שבע|נתניה|ראשון לציון|פתח תקווה|רמת גן|נהריה|יפו|חולון|בת ים)', re.UNICODE),
]

# Time patterns
_TIME_RE = [
    re.compile(r'(\d{1,2}:\d{2})', re.UNICODE),
    re.compile(r'הבוקר|אמש|הלילה|הצהריים|אחה"צ|הערב', re.UNICODE),
]

_EVENT_TYPE_PATTERNS: dict[EventType, list[re.Pattern]] = {
    EventType.fire: [
        re.compile(r'שריפ[הו]|להבות|עשן|כיבוי אש', re.UNICODE),
    ],
    EventType.explosion: [
        re.compile(r'פיצוץ|התפוצצות|פצצה|מטען נפץ', re.UNICODE),
    ],
    EventType.shooting: [
        re.compile(r'ירי|יריות|ירה|נורה|חלל', re.UNICODE),
    ],
    EventType.accident: [
        re.compile(r'תאונ[הת]|התנגשות|פגע ב|קריסת', re.UNICODE),
    ],
    EventType.flood: [
        re.compile(r'שיטפון|הצפ[הי]|גשמים כבדים|נחל', re.UNICODE),
    ],
    EventType.earthquake: [
        re.compile(r'רעידת אדמה|רעש אדמה', re.UNICODE),
    ],
    EventType.protest: [
        re.compile(r'הפגנ[הי]|מחאה|עצרת|מפגינים', re.UNICODE),
    ],
    EventType.terror: [
        re.compile(r'פיגוע|טרור|מחבל|ניסיון פיגוע', re.UNICODE),
    ],
    EventType.crime: [
        re.compile(r'שוד|גניבה|דקירה|נעצר|מעצר|חשוד', re.UNICODE),
    ],
    EventType.medical: [
        re.compile(r'מד"א|אמבולנס|דום לב|פרפור|החייאה', re.UNICODE),
    ],
}


# ── Output dataclass ──────────────────────────────────────────────────────────

@dataclass
class ParsedReport:
    event_type:           EventType        = EventType.unknown
    injured_count:        Optional[int]    = None
    killed_count:         Optional[int]    = None
    affected_people_text: Optional[str]    = None
    event_time_text:      Optional[str]    = None
    location_text:        Optional[str]    = None
    summary:              Optional[str]    = None
    has_media:            bool             = False
    confidence:           float            = 0.0

    # Internal scoring breakdown — useful for debugging
    _score_components: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        return {
            "event_type":           self.event_type.value,
            "injured_count":        self.injured_count,
            "killed_count":         self.killed_count,
            "affected_people_text": self.affected_people_text,
            "event_time_text":      self.event_time_text,
            "location_text":        self.location_text,
            "summary":              self.summary,
            "has_media":            self.has_media,
            "confidence":           round(self.confidence, 3),
        }


# ── Core parser ───────────────────────────────────────────────────────────────

class IncidentParser:
    """
    Stateless parser. Call parse(text, media_items) → ParsedReport.
    All methods are pure functions operating on the input text only.
    """

    def parse(self, text: str, media_items: Optional[list] = None) -> ParsedReport:
        result = ParsedReport()
        scores: dict[str, float] = {}

        result.event_type = self._extract_event_type(text)
        if result.event_type != EventType.unknown:
            scores["event_type"] = 0.25

        result.injured_count = self._extract_count(text, _INJURED_RE)
        result.killed_count  = self._extract_count(text, _KILLED_RE, text_trigger=r'נמצא(?:ה)?\s+גופ')
        if result.injured_count is not None or result.killed_count is not None:
            scores["casualties"] = 0.25

        result.location_text = self._extract_location(text)
        if result.location_text:
            scores["location"] = 0.25

        result.event_time_text = self._extract_time_text(text)
        if result.event_time_text:
            scores["time"] = 0.10

        result.affected_people_text = self._extract_affected_text(text)
        result.summary = self._build_summary(text)
        result.has_media = bool(media_items)
        if result.has_media:
            scores["media"] = 0.05

        result.confidence = min(sum(scores.values()), 1.0)
        result._score_components = scores

        logger.debug(
            f"Parsed: type={result.event_type} injured={result.injured_count} "
            f"killed={result.killed_count} loc={result.location_text!r} "
            f"conf={result.confidence:.2f}"
        )
        return result

    # ── field extractors ──────────────────────────────────────────────────────

    def _extract_event_type(self, text: str) -> EventType:
        for event_type, patterns in _EVENT_TYPE_PATTERNS.items():
            for pat in patterns:
                if pat.search(text):
                    return event_type
        return EventType.unknown

    def _extract_count(
        self,
        text: str,
        patterns: list[re.Pattern],
        text_trigger: Optional[str] = None,
    ) -> Optional[int]:
        """Try each pattern; return first numeric match."""
        for pat in patterns:
            m = pat.search(text)
            if m:
                try:
                    groups = m.groups()
                    if groups:
                        val = _parse_number(groups[0])
                        if val is not None:
                            return val
                    elif text_trigger and re.search(text_trigger, text, re.UNICODE):
                        return 1  # body found → 1 killed
                except (IndexError, ValueError):
                    continue
        return None

    def _extract_location(self, text: str) -> Optional[str]:
        # Try rich patterns first (with context words)
        for pat in _LOCATION_RE[:1]:
            m = pat.search(text)
            if m:
                loc = m.group(1).strip().rstrip(".")
                if len(loc) >= 2:
                    return loc

        # Try city name patterns
        for pat in _LOCATION_RE[1:]:
            m = pat.search(text)
            if m:
                # Strip leading ב
                loc = m.group(0).lstrip("ב").strip()
                if loc:
                    return loc
        return None

    def _extract_time_text(self, text: str) -> Optional[str]:
        for pat in _TIME_RE:
            m = pat.search(text)
            if m:
                return m.group(0)
        return None

    def _extract_affected_text(self, text: str) -> Optional[str]:
        """Extract a short phrase describing who was affected."""
        patterns = [
            re.compile(r'(?:גבר|אישה|ילד|ילדה|נהג|רוכב|חייל|שוטר)[^.،،]{0,40}(?:נפצע|נהרג|פונה|נורה)', re.UNICODE),
            re.compile(r'(?:פצוע|הרוג|נפגע)\s+(?:בן|בת)\s+\d+', re.UNICODE),
        ]
        for pat in patterns:
            m = pat.search(text)
            if m:
                return m.group(0).strip()
        return None

    def _build_summary(self, text: str) -> str:
        """Return the first 200 characters as a summary."""
        cleaned = re.sub(r'\s+', ' ', text).strip()
        return cleaned[:200] + ("..." if len(cleaned) > 200 else "")


# ── Module-level singleton ────────────────────────────────────────────────────

_parser = IncidentParser()


def parse_report(text: str, media_items: Optional[list] = None) -> ParsedReport:
    """Public entry point. Returns a ParsedReport."""
    try:
        return _parser.parse(text, media_items)
    except Exception as e:
        logger.error(f"Parser error: {e}")
        return ParsedReport(summary=text[:200], confidence=0.0)
