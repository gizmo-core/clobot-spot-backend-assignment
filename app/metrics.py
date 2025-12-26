from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from prometheus_client import Counter, Gauge, Histogram

ACTIVE_WINDOW_SEC = float(os.getenv("ACTIVE_WINDOW_SEC", "10"))

mqtt_messages_received_total = Counter(
    "mqtt_messages_received_total",
    "Total MQTT messages received",
)
robot_status_valid_total = Counter(
    "robot_status_valid_total",
    "Total valid robot status messages",
)
robot_status_invalid_total = Counter(
    "robot_status_invalid_total",
    "Total invalid robot status messages",
    ["reason"],
)
db_insert_total = Counter(
    "db_insert_total",
    "Total DB inserts",
)
db_insert_fail_total = Counter(
    "db_insert_fail_total",
    "Total DB insert failures",
)
robot_status_updates_total = Counter(
    "robot_status_updates_total",
    "Robot status updates by driving status",
    ["driving_status"],
)
robot_message_lag_seconds = Histogram(
    "robot_message_lag_seconds",
    "Lag between payload timestamp and server receive time",
    buckets=[0.1, 0.25, 0.5, 1, 2, 5, 10],
)
robots_active = Gauge(
    "robots_active",
    "Robots seen within active window",
)
robots_stale = Gauge(
    "robots_stale",
    "Robots not seen within active window",
)
sse_subscribers = Gauge(
    "sse_subscribers",
    "Current SSE subscribers",
)

_last_seen: dict[str, float] = {}


def update_last_seen(serial_number: str, now: float | None = None) -> None:
    now_ts = time.time() if now is None else now
    _last_seen[serial_number] = now_ts
    active = sum(1 for ts in _last_seen.values() if now_ts - ts <= ACTIVE_WINDOW_SEC)
    stale = len(_last_seen) - active
    robots_active.set(active)
    robots_stale.set(stale)


def observe_message_lag(message_ts: datetime) -> None:
    if message_ts.tzinfo is None:
        message_ts = message_ts.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    lag = (now - message_ts).total_seconds()
    robot_message_lag_seconds.observe(max(lag, 0.0))
