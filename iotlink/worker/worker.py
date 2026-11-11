"""Generate motor telemetry and publish it to a compatible master API."""

from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def positive(name: str, value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return number


def settings(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    url = required(env, "IOTLINK_MASTER_URL")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("IOTLINK_MASTER_URL must have an HTTP(S) scheme and host")
    if parsed.username or parsed.password:
        raise ValueError("IOTLINK_MASTER_URL must not contain credentials")

    run_once = required(env, "IOTLINK_RUN_ONCE").lower()
    if run_once not in ("true", "false"):
        raise ValueError("IOTLINK_RUN_ONCE must be true or false")

    return {
        "url": url,
        "interval": positive(
            "IOTLINK_GENERATION_INTERVAL_SECONDS",
            required(env, "IOTLINK_GENERATION_INTERVAL_SECONDS"),
        ),
        "timeout": positive(
            "IOTLINK_HTTP_TIMEOUT_SECONDS",
            required(env, "IOTLINK_HTTP_TIMEOUT_SECONDS"),
        ),
        "once": run_once == "true",
    }


def generate_batch(sequence: int, timestamp: datetime | None = None) -> dict[str, Any]:
    if sequence < 1:
        raise ValueError("sequence must be positive")

    moment = (timestamp or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    readings = []
    for index, motor in enumerate((
        {"device_id": "motor-01", "temperature": 47.0, "vibration": 1.9, "rpm": 1450},
        {"device_id": "motor-02", "temperature": 51.0, "vibration": 2.3, "rpm": 1490},
    )):
        phase = sequence / 5 + index
        fault = min(sequence * 0.045, 3.5) if index == 1 else 0.0
        readings.append({
            "device_id": motor["device_id"],
            "timestamp": moment,
            "quality": "good",
            "values": {
                "temperature_c": round(motor["temperature"] + math.sin(phase) * 0.8 + fault * 1.2, 2),
                "vibration_mm_s": round(motor["vibration"] + math.sin(phase * 1.7) * 0.2 + fault, 2),
                "rpm": round(motor["rpm"] + math.sin(phase) * 8),
            },
        })

    return {
        "schema_version": "1.0",
        "source": "iotlink-worker",
        "generated_at": moment,
        "readings": readings,
    }


def publish(url: str, batch: dict[str, Any], timeout: float) -> int:
    data = json.dumps(batch, allow_nan=False).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        if response.status != 202:
            raise ValueError(f"Unexpected response status: {response.status}")
        reply = json.load(response)
    accepted = reply.get("accepted") if isinstance(reply, dict) else None
    if type(accepted) is not int or accepted != len(batch["readings"]):
        raise ValueError("The master did not acknowledge all readings")
    return accepted


def log(level: str, event: str, **fields: Any) -> None:
    print(
        json.dumps({"level": level, "event": event, **fields}, ensure_ascii=False),
        file=sys.stderr if level == "error" else sys.stdout,
        flush=True,
    )


def main() -> int:
    try:
        configuration = settings()
    except ValueError as exc:
        log("error", "invalid_configuration", message=str(exc))
        return 2

    sequence = 0
    while True:
        sequence += 1
        batch = generate_batch(sequence)
        log("info", "generated", sequence=sequence, readings=len(batch["readings"]))
        success = True
        try:
            accepted = publish(configuration["url"], batch, configuration["timeout"])
            log("info", "published", sequence=sequence, accepted=accepted)
        except (OSError, ValueError) as exc:
            success = False
            log("error", "publish_failed", sequence=sequence, message=str(exc))

        if configuration["once"]:
            return 0 if success else 1
        time.sleep(configuration["interval"])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("info", "stopped")
