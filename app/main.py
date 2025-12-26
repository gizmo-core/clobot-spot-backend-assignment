import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.api.routes import router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.models import Base
from app.db.session import engine
from app.metrics import ACTIVE_REFRESH_SEC, recompute_active_stale
from app.mqtt.subscriber import mqtt_subscriber
from app.sse.manager import SSEManager

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    app.state.sse_manager = SSEManager()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("SELECT 1"))
    app.state.mqtt_task = asyncio.create_task(
        mqtt_subscriber(settings, app.state.sse_manager)
    )
    app.state.metrics_task = None
    if ACTIVE_REFRESH_SEC > 0:
        app.state.metrics_task = asyncio.create_task(
            _active_stale_refresher(ACTIVE_REFRESH_SEC)
        )
    try:
        yield
    finally:
        task: asyncio.Task | None = getattr(app.state, "mqtt_task", None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        metrics_task: asyncio.Task | None = getattr(app.state, "metrics_task", None)
        if metrics_task:
            metrics_task.cancel()
            try:
                await metrics_task
            except asyncio.CancelledError:
                pass


app = FastAPI(lifespan=lifespan)
app.include_router(router)
Instrumentator().instrument(app).expose(app, include_in_schema=False)


async def _active_stale_refresher(interval_sec: float) -> None:
    interval = max(interval_sec, 1.0)
    while True:
        recompute_active_stale()
        await asyncio.sleep(interval)
