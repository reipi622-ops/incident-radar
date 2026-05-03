# Incident Radar — Architecture

## מה המערכת עושה

מקבלת דיווחים גולמיים ממקורות פומביים, מחלצת מהם מידע מובנה, מאחדת כפילויות לאירוע יחיד, ומציגה הכל על מפה עם ציר זמן.

---

## זרימת מידע

```
[מקור פומבי / JSON מקומי]
         │
         ▼
   [Collector]
   אוסף raw_reports
   שומר content_hash למניעת כפילויות
         │
         ▼
   [Parser]
   מחלץ: event_type / location / casualties / time
   מייצר confidence_score
         │
         ▼
   [Dedup Engine]
   משווה לאירועים קיימים לפי:
   text_similarity + time_proximity + location_match
         │
    ┌────┴────┐
    ▼         ▼
[Event חדש] [עדכון לאירוע קיים]
    │         │
    └────┬────┘
         ▼
   [Geocoding]
   location_text → lat/lng + confidence
         │
         ▼
   [API — FastAPI]
   /events /events/map /stats /pipeline
         │
         ▼
   [Frontend — React + Leaflet]
   מפה | טבלה | פרטי אירוע | ציר זמן
```

---

## ישויות ויחסים

```
sources          1 ──< raw_reports
raw_reports      M >──< events          (via event_reports)
events           1 ──< event_updates
events           1 ──< event_media
events           1 ──< locations        (geocoded)
raw_reports      M ──< people_mentioned
```

### sources
מקורות דיווח רשומים. כל collector נרשם כאן.

| שדה | תפקיד |
|-----|--------|
| name | מזהה ייחודי |
| type | rss / api / mock / manual |
| is_active | האם פעיל |

### raw_reports
דיווח גולמי, immutable לאחר שמירה.

| שדה | תפקיד |
|-----|--------|
| content_hash | SHA-256, מונע כפילות |
| raw_text | הטקסט המלא |
| media_json | [{url, type, caption}] |
| is_parsed | false עד שה-parser מטפל |

### events
אירוע מעובד ומנורמל — מה שמוצג על המפה.

| שדה | תפקיד |
|-----|--------|
| event_type | fire/shooting/accident/... |
| status | new → updated → verified |
| parser_confidence | 0.0–1.0 |
| geocode_confidence | 0.0–1.0 |
| latitude/longitude | לאחר geocoding |

### event_reports
join table — איזה raw_reports שייכים לאיזה event.

| שדה | תפקיד |
|-----|--------|
| relation_type | primary / update / duplicate |
| dedup_score | 0.0–1.0 |
| dedup_reason | הסבר טקסטואלי |

### event_updates
audit trail — כל שינוי בשדה של event.

| שדה | תפקיד |
|-----|--------|
| field_name | איזה שדה השתנה |
| old_value / new_value | לפני ואחרי |
| source_report_id | מה גרם לשינוי |

### event_media
מדיה משויכת — URL בלבד, ללא הורדה.

| שדה | תפקיד |
|-----|--------|
| media_type | image / video |
| media_url | קישור מקורי |

### locations
geocoded locations עם provider metadata.

| שדה | תפקיד |
|-----|--------|
| query_text | מה נשלח ל-geocoder |
| provider | nominatim / ... |
| confidence | 0.0–1.0 |

### people_mentioned
אנשים שמוזכרים בדיווחים — לעתיד.

| שדה | תפקיד |
|-----|--------|
| role | injured / killed / suspect |
| mention_text | ציטוט מקורי |

---

## Indexes קריטיים

```sql
raw_reports: content_hash, raw_timestamp, is_parsed
events:      event_time, location_text, status, (lat, lng)
event_reports: event_id, raw_report_id
```

---

## Deduplication — לוגיקת ציון

```
score = (text_similarity  × 0.40)
      + (time_proximity   × 0.25)
      + (location_match   × 0.20)
      + (type_match       × 0.10)
      + (casualty_match   × 0.05)

score ≥ 0.90 → duplicate
score ≥ 0.60 → update
score < 0.60 → new event
```

---

## API Endpoints

```
GET  /health
GET  /sources           POST /sources
GET  /raw-reports
GET  /events            GET /events/{id}     GET /events/map
GET  /stats/summary
POST /pipeline/collect/run
POST /pipeline/parse/run
POST /pipeline/dedup/run
POST /pipeline/geocode/run
POST /pipeline/run-all
```

---

## מגבלות MVP

- Nominatim rate-limited: 1 req/sec
- Parser: regex בלבד, ללא LLM
- Collector: mock JSON + RSS בלבד
- אין auth
- אין real-time (polling בלבד)

---

## שלבים הבאים

1. RSS collector אמיתי
2. LLM layer מעל הparser
3. PostGIS לשאילתות מרחביות
4. WebSocket לעדכונים real-time
5. Auth + roles
