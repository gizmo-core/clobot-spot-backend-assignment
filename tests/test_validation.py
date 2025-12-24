from uuid import uuid4

import pytest

from app.schemas.robot_status import RobotStatusIn


def _base_payload() -> dict:
    return {
        "timestamp": "2025-12-01T00:00:00Z",
        "battery_level": 50,
        "battery_status": "CHARGING",
        "driving_status": "IDLE",
        "current_drive_id": None,
        "location": {"latitude": 1.0, "longitude": 2.0, "height": 3.0},
    }


def test_moving_requires_drive_id() -> None:
    payload = _base_payload()
    payload["driving_status"] = "MOVING"
    payload["current_drive_id"] = None
    with pytest.raises(ValueError):
        RobotStatusIn.model_validate(payload)


def test_idle_rejects_drive_id() -> None:
    payload = _base_payload()
    payload["driving_status"] = "IDLE"
    payload["current_drive_id"] = str(uuid4())
    with pytest.raises(ValueError):
        RobotStatusIn.model_validate(payload)
