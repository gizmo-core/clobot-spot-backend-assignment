import asyncio
import json
import logging

from aiomqtt import Client, MqttError, ProtocolVersion
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.db.queries import insert_robot_status
from app.db.session import AsyncSessionLocal
from app.schemas.robot_status import RobotStatusIn, RobotStatusOut
from app.sse.manager import SSEManager

logger = logging.getLogger(__name__)


def _extract_serial(topic: str) -> str | None:
    parts = topic.split("/")
    if len(parts) != 3:
        return None
    if parts[0] != "robot" or parts[2] != "status":
        return None
    return parts[1]


async def mqtt_subscriber(settings: Settings, sse_manager: SSEManager) -> None:
    backoff = 1
    while True:
        try:
            logger.info(
                "Connecting to MQTT broker %s:%s",
                settings.mqtt_host,
                settings.mqtt_port,
            )
            async with Client(
                hostname=settings.mqtt_host,
                port=settings.mqtt_port,
                username=settings.mqtt_username,
                password=settings.mqtt_password,
                protocol=ProtocolVersion.V5,
            ) as client:
                logger.info(
                    "MQTT connected (username=%s)",
                    settings.mqtt_username or "anonymous",
                )

                await client.subscribe("robot/+/status")
                logger.info("Subscribed to topic robot/+/status")

                backoff = 1
                async for message in client.messages:
                    logger.debug(
                        "Message received: topic=%s payload=%s",
                        message.topic.value,
                        message.payload,
                    )
                    serial_number = _extract_serial(message.topic.value)
                    if not serial_number:
                        logger.warning(
                            "Invalid topic received: %s", message.topic.value
                        )
                        continue
                    try:
                        payload = json.loads(message.payload.decode("utf-8"))
                        status = RobotStatusIn.model_validate(payload)
                    except (json.JSONDecodeError, ValidationError) as exc:
                        logger.warning("Validation failed: %s", exc)
                        continue

                    async with AsyncSessionLocal() as session:
                        try:
                            await insert_robot_status(
                                session, serial_number, status, payload
                            )
                            await session.commit()
                        except SQLAlchemyError:
                            await session.rollback()
                            logger.exception(
                                "DB insert failed for serial=%s", serial_number
                            )
                            continue

                    out = RobotStatusOut(
                        serial_number=serial_number,
                        ts=status.ts,
                        battery_level=status.battery_level,
                        battery_status=status.battery_status,
                        driving_status=status.driving_status,
                        current_drive_id=status.current_drive_id,
                        location=status.location,
                        payload=payload,
                    )
                    sse_manager.broadcast(
                        serial_number, out.model_dump_json(by_alias=True)
                    )
        except MqttError as exc:
            logger.warning("MQTT error: %s. reconnecting in %ss", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
        except Exception:
            logger.exception("Unexpected error in mqtt_subscriber. reconnecting in %ss", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)            
