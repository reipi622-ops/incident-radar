from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger

from app.core.config import settings
from app.api import health, sources, reports, events, stats, pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.collectors.telegram_collector import build_telegram_collectors
    import asyncio

    logger.info("Starting Incident Radar API...")

    collectors = build_telegram_collectors()

    async def run_all():
        await asyncio.gather(*[c.collect() for c in collectors])

    task = asyncio.create_task(run_all())

    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    logger.info("Shutting down...")


app = FastAPI(
    title="Incident Radar API",
    description="Collects, parses, and maps incident reports from public sources.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(sources.router, prefix="/sources", tags=["sources"])
app.include_router(reports.router, prefix="/raw-reports", tags=["raw-reports"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(stats.router, prefix="/stats", tags=["stats"])
app.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])
