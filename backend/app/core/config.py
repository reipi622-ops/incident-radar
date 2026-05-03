from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "Incident Radar"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://radar:radar@db:5432/incident_radar"

    # CORS — accepts either a JSON array string or comma-separated values
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://frontend:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except Exception:
                return [i.strip() for i in v.split(",")]
        return v

    # Geocoding
    GEOCODING_PROVIDER: str = "nominatim"
    NOMINATIM_USER_AGENT: str = "incident-radar-mvp"
    GEOCODING_MIN_CONFIDENCE: float = 0.5

    # Deduplication
    DEDUP_TIME_WINDOW_HOURS: int = 24
    DEDUP_TEXT_SIMILARITY_THRESHOLD: float = 0.65
    DEDUP_LOCATION_RADIUS_KM: float = 10.0
    DEDUP_MIN_SCORE: float = 0.6

    # Logging
    LOG_LEVEL: str = "INFO"


settings = Settings()
