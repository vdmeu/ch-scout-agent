from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import settings
from src.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only start the scheduler in non-test environments
    scheduler = None
    if settings.app_env != "test":
        from src.scheduler import create_scheduler

        scheduler = create_scheduler()
        scheduler.start()
        logger.info("scheduler_started", jobs=len(scheduler.get_jobs()))

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")


app = FastAPI(
    title="CH Scout Agent",
    description=(
        "Customer acquisition scout: monitors developer forums for Companies House "
        "pain points and sends Discord alerts with draft replies."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"], openapi_extra={"security": []})
async def health():
    """Health check — Railway uses this to confirm the service is running."""
    return {
        "status": "ok",
        "service": "ch-scout-agent",
        "environment": settings.app_env,
    }
