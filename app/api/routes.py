import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from app.db.queries import fetch_robot_history
from app.db.session import AsyncSessionLocal
from app.sse.manager import SSEManager

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_datetime(value: str) -> datetime:
    value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


@router.get("/robots/{serial_number}/feed")
async def robot_feed(serial_number: str, request: Request) -> StreamingResponse:
    manager: SSEManager = request.app.state.sse_manager
    queue = manager.register(serial_number)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            while True:
                data = await queue.get()
                yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            manager.unregister(serial_number, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/robots/{serial_number}/history")
async def robot_history(
    serial_number: str,
    start_time: str = Query(...),
    end_time: str = Query(...),
    include_payload: bool = Query(False),
    limit: int = Query(500, ge=1, le=5000),
) -> list[dict]:
    try:
        start_dt = _parse_datetime(start_time)
        end_dt = _parse_datetime(end_time)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")
    if end_dt < start_dt:
        raise HTTPException(status_code=400, detail="end_time must be >= start_time")

    async with AsyncSessionLocal() as session:
        items = await fetch_robot_history(
            session, serial_number, start_dt, end_dt, include_payload, limit
        )

    return [item.model_dump(by_alias=True) for item in items]


@router.get("/health")
async def health() -> dict:
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok"}
