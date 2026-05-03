"""
Tests for the parsing engine.
Run: pytest backend/tests/test_parser.py -v
"""
import pytest
from app.parsers.parser import parse_report, IncidentParser
from app.models.models import EventType


@pytest.fixture
def parser():
    return IncidentParser()


# ── Event type detection ──────────────────────────────────────────────────────

class TestEventTypeDetection:
    def test_fire(self, parser):
        result = parser.parse("שריפה פרצה בבניין ברחוב הרצל")
        assert result.event_type == EventType.fire

    def test_explosion(self, parser):
        result = parser.parse("פיצוץ חזק נשמע בתחנת הדלק בחיפה")
        assert result.event_type == EventType.explosion

    def test_shooting(self, parser):
        result = parser.parse("ירי ביפו, גבר נורה ופונה לבית חולים")
        assert result.event_type == EventType.shooting

    def test_accident(self, parser):
        result = parser.parse("תאונת דרכים קשה בכביש 1 ליד שפיים")
        assert result.event_type == EventType.accident

    def test_flood(self, parser):
        result = parser.parse("שיטפון בנחל קישון לאחר גשמים כבדים")
        assert result.event_type == EventType.flood

    def test_earthquake(self, parser):
        result = parser.parse("רעידת אדמה בעוצמה 3.8 הורגשה באזור ים המלח")
        assert result.event_type == EventType.earthquake

    def test_protest(self, parser):
        result = parser.parse("הפגנה גדולה בכיכר רבין, אלפי מפגינים")
        assert result.event_type == EventType.protest

    def test_terror(self, parser):
        result = parser.parse("ניסיון פיגוע בשדה התעופה בן גוריון נכשל")
        assert result.event_type == EventType.terror

    def test_crime(self, parser):
        result = parser.parse("דקירה בשוק מחנה יהודה, חשוד נעצר")
        assert result.event_type == EventType.crime

    def test_unknown_for_vague_text(self, parser):
        result = parser.parse("מצב בטחוני מתוח באזור")
        assert result.event_type == EventType.unknown


# ── Injured count extraction ──────────────────────────────────────────────────

class TestInjuredExtraction:
    def test_digit_before_word(self, parser):
        result = parser.parse("3 פצועים פונו לבית החולים")
        assert result.injured_count == 3

    def test_digit_injured(self, parser):
        result = parser.parse("שריפה בתל אביב, 5 נפגעים")
        assert result.injured_count == 5

    def test_no_injured(self, parser):
        result = parser.parse("רעידת אדמה ללא נפגעים")
        assert result.injured_count is None

    def test_injured_zero_not_extracted(self, parser):
        # "אין נפגעים" — no digit to extract
        result = parser.parse("אין נפגעים דווחו")
        assert result.injured_count is None

    def test_large_count(self, parser):
        result = parser.parse("50 פצועים בפיצוץ גדול")
        assert result.injured_count == 50


# ── Killed count extraction ───────────────────────────────────────────────────

class TestKilledExtraction:
    def test_digit_before_harug(self, parser):
        result = parser.parse("2 הרוגים בתאונה בכביש 1")
        assert result.killed_count == 2

    def test_nehragu(self, parser):
        result = parser.parse("שניים נהרגו בתאונה הקשה")
        # word number — currently digit-only; ensure it doesn't crash
        assert result.killed_count is None or result.killed_count == 2

    def test_body_found_trigger(self, parser):
        result = parser.parse("נמצאה גופה של גבר בחוף בנהריה")
        assert result.killed_count == 1

    def test_no_killed(self, parser):
        result = parser.parse("שריפה ללא נפגעים, הכיבוי הצליח")
        assert result.killed_count is None


# ── Location extraction ───────────────────────────────────────────────────────

class TestLocationExtraction:
    def test_city_name(self, parser):
        result = parser.parse("שריפה בחיפה, אין נפגעים")
        assert result.location_text is not None
        assert "חיפה" in result.location_text

    def test_tel_aviv(self, parser):
        result = parser.parse("פיצוץ בתל אביב ברחוב דיזנגוף")
        assert result.location_text is not None
        assert "תל אביב" in result.location_text or "דיזנגוף" in result.location_text

    def test_street_extraction(self, parser):
        result = parser.parse("שריפה ברחוב הרצל 14 בתל אביב, 3 פצועים")
        assert result.location_text is not None

    def test_no_location(self, parser):
        result = parser.parse("אירוע ביטחוני לא מאופיין")
        assert result.location_text is None


# ── Confidence scoring ────────────────────────────────────────────────────────

class TestConfidenceScoring:
    def test_full_report_high_confidence(self, parser):
        text = "שריפה ברחוב הרצל תל אביב. 3 פצועים פונו. כוחות כיבוי בשטח."
        result = parser.parse(text)
        assert result.confidence >= 0.5

    def test_vague_report_low_confidence(self, parser):
        result = parser.parse("אירוע כלשהו")
        assert result.confidence < 0.3

    def test_with_media_raises_confidence(self, parser):
        text = "שריפה בחיפה"
        without = parser.parse(text, media_items=None)
        with_media = parser.parse(text, media_items=[{"url": "http://img.jpg", "type": "image"}])
        assert with_media.confidence > without.confidence


# ── Summary ───────────────────────────────────────────────────────────────────

class TestSummary:
    def test_summary_truncates(self, parser):
        long_text = "א" * 300
        result = parser.parse(long_text)
        assert len(result.summary) <= 203  # 200 + "..."

    def test_short_text_no_ellipsis(self, parser):
        result = parser.parse("שריפה בחיפה")
        assert not result.summary.endswith("...")


# ── Full report integration ───────────────────────────────────────────────────

class TestFullReportParsing:
    def test_fire_with_casualties_and_location(self):
        text = "שריפה פרצה הבוקר בבניין מגורים ברחוב הרצל 14 בתל אביב. 3 פצועים פונו לאיכילוב."
        result = parse_report(text, media_items=[{"url": "http://x.com/img.jpg", "type": "image"}])
        assert result.event_type == EventType.fire
        assert result.injured_count == 3
        assert result.location_text is not None
        assert result.has_media is True
        assert result.confidence > 0.5

    def test_earthquake_no_casualties(self):
        text = "רעידת אדמה בעוצמה 3.8 הורגשה באזור ים המלח. לא דווח על נפגעים."
        result = parse_report(text)
        assert result.event_type == EventType.earthquake
        assert result.injured_count is None
        assert result.killed_count is None

    def test_parser_does_not_crash_on_empty(self):
        result = parse_report("")
        assert result is not None
        assert result.confidence == 0.0
