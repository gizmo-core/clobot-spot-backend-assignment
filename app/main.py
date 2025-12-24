import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes import router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.models import Base
from app.db.session import engine
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


app = FastAPI(lifespan=lifespan)
app.include_router(router)
