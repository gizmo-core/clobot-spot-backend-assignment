from sqlalchemy import Column, DateTime, Enum, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class RobotStatusHistory(Base):
    __tablename__ = "robot_status_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_number = Column(String, nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False)
    battery_level = Column(Integer, nullable=False)
    battery_status = Column(
        Enum(
            "CHARGING",
            "DISCHARGING",
            name="battery_status_enum",
            create_type=False,
        ),
        nullable=False,
    )
    driving_status = Column(
        Enum(
            "IDLE",
            "MOVING",
            name="driving_status_enum",
            create_type=False,
        ),
        nullable=False,
    )
    current_drive_id = Column(UUID(as_uuid=True), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    payload = Column(JSONB, nullable=True)


Index(
    "idx_robot_status_history_serial_ts",
    RobotStatusHistory.serial_number,
    RobotStatusHistory.ts.desc(),
)
