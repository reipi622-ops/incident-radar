# Incident Radar

מערכת לאיסוף, עיבוד, וניתוח דיווחים על אירועים ממקורות פומביים.

## מה המערכת עושה

1. **אוספת** דיווחים גולמיים ממקורות (כרגע: JSON מקומי)
2. **מחלצת** מידע מובנה: סוג אירוע, נפגעים, מיקום, זמן
3. **מאחדת** כפילויות ועדכונים לאירוע יחיד
4. **ממקמת** אירועים על מפה (Nominatim geocoding)
5. **מציגה** דשבורד, מפה, וטבלה מסוננת

---

## הרצה מהירה

```bash
cp .env.example .env
docker compose up --build
# בדפדפן: http://localhost:3000
# לחץ "הרץ Pipeline" בדשבורד
```

---

## מבנה הפרויקט

```
backend/
  app/
    api/          → FastAPI endpoints
    collectors/   → data collection (base + local_json)
    parsers/      → regex extraction engine
    dedup/        → heuristic matching engine
    geocoding/    → Nominatim abstraction
    models/       → SQLAlchemy ORM
    schemas/      → Pydantic response schemas
    core/         → config, database, logging
  migrations/     → Alembic migrations
  tests/          → pytest unit tests

frontend/
  src/
    app/          → Next.js pages (dashboard, map, events)
    components/   → MapView, MiniMap, shared UI
    utils/        → api client, event helpers
    types/        → TypeScript types

sample_data/
  mock_reports.json   → 5 דיווחי דמו
docs/
  architecture.md
```

---

## API Endpoints

| Method | Path | תיאור |
|--------|------|--------|
| GET | /health | בדיקת חיות |
| GET | /sources | רשימת מקורות |
| POST | /sources | הוספת מקור |
| GET | /raw-reports | דיווחים גולמיים |
| GET | /events | רשימת אירועים |
| GET | /events/map | נקודות מפה בלבד |
| GET | /events/{id} | פרטי אירוע |
| GET | /stats/summary | סיכום סטטיסטי |
| POST | /pipeline/collect/run | איסוף |
| POST | /pipeline/parse/run | פרסור |
| POST | /pipeline/dedup/run | דדופ |
| POST | /pipeline/geocode/run | גיאוקודינג |
| POST | /pipeline/run-all | כל הפייפליין |

---

## זרימת מידע

```
JSON → Collector → raw_reports → Parser → Dedup → Event
                                                     ↓
                                              Geocoding → lat/lng
                                                     ↓
                                             API → Frontend
```

## Deduplication — ציון

```
text_similarity  × 0.40
time_proximity   × 0.25
location_match   × 0.20
type_match       × 0.10
casualty_match   × 0.05

≥ 0.90 → duplicate
≥ 0.60 → update לאירוע קיים
< 0.60 → אירוע חדש
```

---

## בדיקות

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

---

## מגבלות MVP

- Parser: regex בלבד, ללא LLM
- Geocoding: Nominatim, מוגבל ל-1 req/sec
- Collector: JSON מקומי בלבד
- אין auth, אין real-time

---

## שלבים הבאים

1. RSS/API collector אמיתי
2. LLM layer מעל ה-parser
3. PostGIS לשאילתות גיאוגרפיות
4. WebSocket לעדכונים חיים
5. Auth + roles
