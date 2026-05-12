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
    # ב + context word + location name
    re.compile(
        r'ב(?:רחוב|שכונת|עיר|כפר|מושב|ישוב|אזור|אתר|כביש|צומת|שדה|בניין|פארק|גן|נמל|שוק|מרכז|קניון|בית)\s+([֐-׿\w\s\-״\'\"]{2,40})',
        re.UNICODE
    ),
    # ב + known city
    re.compile(
        r'ב(?:תל אביב|חיפה|ירושלים|באר שבע|נתניה|ראשון לציון|פתח תקווה|רמת גן|נהריה|יפו|'
        r'אשדוד|אשקלון|הרצליה|כפר סבא|רעננה|הוד השרון|רמת השרון|גבעתיים|בני ברק|'
        r'בת ים|חולון|לוד|רמלה|מודיעין|אילת|טבריה|צפת|עכו|נצרת|אום אל פחם|'
        r'קריית שמונה|קריית גת|קריית ביאליק|קריית מוצקין|קריית אתא|'
        r'רחובות|נס ציונה|יבנה|גדרה|רהט|שפרעם|מגדל העמק|עפולה|'
        r'דימונה|ערד|בית שמש|גבעת שמואל|אור יהודה|אלעד)',
        re.UNICODE
    ),
    # city standalone
    re.compile(
        r'(?<![\u05d0-\u05ea])(?:תל אביב|חיפה|ירושלים|באר שבע|נתניה|ראשון לציון|פתח תקווה|רמת גן|נהריה|יפו|'
        r'אשדוד|אשקלון|הרצליה|כפר סבא|רעננה|בת ים|חולון|לוד|רמלה|מודיעין|אילת|'
        r'טבריה|צפת|עכו|נצרת|רחובות|נס ציונה|יבנה|דימונה|ערד|בית שמש)(?![\u05d0-\u05ea])',
        re.UNICODE
    ),
    # ב + any Hebrew word(s) -- broad fallback
    re.compile(r'\bב([א-ת]{2,15}(?:\s[א-ת]{2,15}){0,2})\b', re.UNICODE),
    # Arabic: في (fi/in) + location
    re.compile(
        r'[في]\s+([\u0600-\u06ff]{2,20}(?:\s[\u0600-\u06ff]{2,20}){0,2})',
        re.UNICODE
    ),
    # Arabic city names standalone
    re.compile(
        r'(?:جنين|نابلس|رام الله|الخليل|طولكرم|قلقيلية|حيفا|غزة|القدس|أريحا)',
        re.UNICODE
    ),
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
        # Pattern 1: ב + context word + location name (has capture group)
        m = _LOCATION_RE[0].search(text)
        if m:
            loc = m.group(1).strip().rstrip(".")
            if len(loc) >= 2:
                logger.debug(f"loc pat1: {loc!r}")
                return loc

        # Patterns 2-3: known city names (no capture group)
        for pat in _LOCATION_RE[1:3]:
            m = pat.search(text)
            if m:
                loc = m.group(0).lstrip("ב").strip()
                if loc:
                    logger.debug(f"loc pat2/3: {loc!r}")
                    return loc

        # Pattern 4: ב + any Hebrew word(s) (has capture group)
        m = _LOCATION_RE[3].search(text)
        if m:
            loc = m.group(1).strip()
            if len(loc) >= 2:
                logger.debug(f"loc pat4: {loc!r}")
                return loc

        # Pattern 5: Arabic في + location (has capture group)
        m = _LOCATION_RE[4].search(text)
        if m:
            loc = m.group(1).strip()
            if len(loc) >= 2:
                logger.debug(f"loc arabic-fi: {loc!r}")
                return loc

        # Pattern 6: Arabic city names standalone (no capture group)
        m = _LOCATION_RE[5].search(text)
        if m:
            loc = m.group(0).strip()
            if loc:
                logger.debug(f"loc arabic-city: {loc!r}")
                return loc

        # Fallback: Hebrew/Arabic words after separator | — : –
        sep = re.search(
            r"[|—–\-:] *([\u0590-\u05ff\u0600-\u06ff][\u0590-\u05ff\u0600-\u06ff\s]{1,30})",
            text, re.UNICODE
        )
        if sep:
            loc = sep.group(1).strip()
            if len(loc) >= 2:
                logger.debug(f"loc sep: {loc!r}")
                return loc

        logger.debug(f"loc: no match in {text[:80]!r}")
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
