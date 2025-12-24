from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BatteryStatus(StrEnum):
    CHARGING = "CHARGING"
    DISCHARGING = "DISCHARGING"


class DrivingStatus(StrEnum):
    IDLE = "IDLE"
    MOVING = "MOVING"


class Location(BaseModel):
    latitude: float
    longitude: float
    height: float


class RobotStatusIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    ts: datetime | None = Field(default=None, alias="timestamp")
    battery_level: int = Field(ge=1, le=100)
    battery_status: BatteryStatus
    driving_status: DrivingStatus
    current_drive_id: UUID | None = None
    location: Location

    @model_validator(mode="after")
    def validate_drive_id(self) -> "RobotStatusIn":
        if self.driving_status == DrivingStatus.MOVING and self.current_drive_id is None:
            raise ValueError("current_drive_id is required when driving_status is MOVING")
        if self.driving_status == DrivingStatus.IDLE and self.current_drive_id is not None:
            raise ValueError("current_drive_id must be null when driving_status is IDLE")
        if self.ts is None:
            self.ts = datetime.now(timezone.utc)
        return self


class RobotStatusOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    serial_number: str
    ts: datetime = Field(alias="timestamp")
    battery_level: int
    battery_status: BatteryStatus
    driving_status: DrivingStatus
    current_drive_id: UUID | None
    location: Location
    payload: dict[str, Any] | None = None
