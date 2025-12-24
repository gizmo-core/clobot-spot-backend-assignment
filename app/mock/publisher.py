import asyncio
import json
import logging
import os
import random
import time
import uuid
from datetime import datetime, timezone
from itertools import cycle

from aiomqtt import Client, MqttError, ProtocolVersion

logger = logging.getLogger(__name__)


def _bool_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _load_settings() -> dict:
    return {
        "mqtt_host": os.getenv("MQTT_HOST", "localhost"),
        "mqtt_port": int(os.getenv("MQTT_PORT", "1883")),
        "mqtt_username": os.getenv("MQTT_USERNAME"),
        "mqtt_password": os.getenv("MQTT_PASSWORD"),
        "robot_count": int(os.getenv("ROBOT_COUNT", "2")),
        "publish_interval_sec": float(os.getenv("PUBLISH_INTERVAL_SEC", "1.0")),
        "invalid_rate": float(os.getenv("INVALID_RATE", "0.0")),
        "jitter_max_sec": float(os.getenv("JITTER_MAX_SEC", "0.2")),
        "stats_interval_env": os.getenv("STATS_LOG_INTERVAL_SEC"),
        "stats_enabled": _bool_env(os.getenv("ENABLE_STATS_LOG")),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }


def _init_robot_state() -> dict:
    return {
        "latitude": 37.4 + random.uniform(0, 0.01),
        "longitude": 127.1 + random.uniform(0, 0.01),
        "height": 0.0,
        "battery_level": 100,
        "driving_status": "IDLE",
        "current_drive_id": None,
    }


def _update_robot_state(state: dict) -> dict:
    if random.random() < 0.1:
        if state["driving_status"] == "IDLE":
            state["driving_status"] = "MOVING"
            state["current_drive_id"] = str(uuid.uuid4())
        else:
            state["driving_status"] = "IDLE"
            state["current_drive_id"] = None

    if state["driving_status"] == "MOVING":
        state["battery_level"] = max(1, state["battery_level"] - 1)
        battery_status = "DISCHARGING"
        state["latitude"] += random.uniform(-0.00005, 0.00005)
        state["longitude"] += random.uniform(-0.00005, 0.00005)
        state["height"] = round(random.uniform(0, 0.5), 2)
    else:
        state["battery_level"] = min(100, state["battery_level"] + 1)
        battery_status = "CHARGING"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "battery_level": state["battery_level"],
        "battery_status": battery_status,
        "driving_status": state["driving_status"],
        "current_drive_id": state["current_drive_id"],
        "location": {
            "latitude": round(state["latitude"], 6),
            "longitude": round(state["longitude"], 6),
            "height": state["height"],
        },
    }


def _maybe_make_invalid(payload: dict, invalid_rate: float) -> dict:
    if invalid_rate <= 0:
        return payload
    if random.random() >= invalid_rate:
        return payload
    if payload["driving_status"] == "MOVING":
        payload["current_drive_id"] = None
    else:
        payload["current_drive_id"] = str(uuid.uuid4())
    return payload


async def _publish_loop(client: Client, settings: dict) -> None:
    robot_count = settings["robot_count"]
    if robot_count <= 0:
        logger.warning("ROBOT_COUNT must be >= 1")
        return

    publish_interval_sec = max(settings["publish_interval_sec"], 0.1)
    tick = max(publish_interval_sec / robot_count, 0.01)
    jitter_max = max(settings["jitter_max_sec"], 0.0)
    invalid_rate = max(min(settings["invalid_rate"], 1.0), 0.0)

    stats_interval_env = settings["stats_interval_env"]
    stats_interval_sec = (
        float(stats_interval_env) if stats_interval_env is not None else 5.0
    )
    stats_enabled = settings["stats_enabled"] or stats_interval_env is not None

    serials = [f"ROBOT-{i:04d}" for i in range(1, robot_count + 1)]
    states = {serial: _init_robot_state() for serial in serials}
    serial_cycle = cycle(serials)

    logger.info(
        "Publisher started robot_count=%s interval=%.2fs tick=%.3fs invalid_rate=%.2f",
        robot_count,
        publish_interval_sec,
        tick,
        invalid_rate,
    )

    total_published = 0
    start_time = time.monotonic()
    last_stats = start_time

    for serial in serial_cycle:
        payload = _update_robot_state(states[serial])
        payload["robot_id"] = serial
        payload = _maybe_make_invalid(payload, invalid_rate)
        topic = f"robot/{serial}/status"
        await client.publish(topic, payload=json.dumps(payload))
        total_published += 1

        now = time.monotonic()
        if stats_enabled and now - last_stats >= stats_interval_sec:
            elapsed = max(now - start_time, 0.001)
            rate = total_published / elapsed
            logger.info(
                "Published total=%s rate=%.2f msg/s",
                total_published,
                rate,
            )
            last_stats = now

        await asyncio.sleep(tick + random.uniform(0, jitter_max))


async def run() -> None:
    settings = _load_settings()
    logging.basicConfig(
        level=settings["log_level"],
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    backoff = 1
    while True:
        try:
            logger.info(
                "Connecting to MQTT broker %s:%s",
                settings["mqtt_host"],
                settings["mqtt_port"],
            )
            async with Client(
                hostname=settings["mqtt_host"],
                port=settings["mqtt_port"],
                username=settings["mqtt_username"],
                password=settings["mqtt_password"],
                protocol=ProtocolVersion.V5,
            ) as client:
                logger.info("MQTT connected")
                backoff = 1
                await _publish_loop(client, settings)
        except MqttError as exc:
            logger.warning("MQTT error: %s. reconnecting in %ss", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
