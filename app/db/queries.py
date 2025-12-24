from datetime import datetime

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RobotStatusHistory
from app.schemas.robot_status import Location, RobotStatusIn, RobotStatusOut


async def insert_robot_status(
    session: AsyncSession,
    serial_number: str,
    status: RobotStatusIn,
    payload: dict | None,
) -> None:
    await session.execute(
        insert(RobotStatusHistory).values(
            serial_number=serial_number,
            ts=status.ts,
            battery_level=status.battery_level,
            battery_status=status.battery_status.value,
            driving_status=status.driving_status.value,
            current_drive_id=status.current_drive_id,
            latitude=status.location.latitude,
            longitude=status.location.longitude,
            height=status.location.height,
            payload=payload,
        )
    )


async def fetch_robot_history(
    session: AsyncSession,
    serial_number: str,
    start_time: datetime,
    end_time: datetime,
    include_payload: bool,
    limit: int,
) -> list[RobotStatusOut]:
    stmt = (
        select(RobotStatusHistory)
        .where(RobotStatusHistory.serial_number == serial_number)
        .where(RobotStatusHistory.ts.between(start_time, end_time))
        .order_by(RobotStatusHistory.ts.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    items: list[RobotStatusOut] = []
    for row in rows:
        items.append(
            RobotStatusOut(
                serial_number=row.serial_number,
                ts=row.ts,
                battery_level=row.battery_level,
                battery_status=row.battery_status,
                driving_status=row.driving_status,
                current_drive_id=row.current_drive_id,
                location=Location(
                    latitude=row.latitude,
                    longitude=row.longitude,
                    height=row.height,
                ),
                payload=row.payload if include_payload else None,
            )
        )
    return items
