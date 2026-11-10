"""Worker de adquisición. Consumo HTTP de un maestro o adaptador compatible."""
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


def _positive(name: str, raw: str) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} debe ser numérico") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} debe ser mayor que cero")
    return value


def settings(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    mode = env.get("IOTLINK_MASTER_MODE", "simulated").strip().lower()
    if mode not in ("simulated", "real"):
        raise ValueError("IOTLINK_MASTER_MODE debe ser simulated o real")
    if mode == "real":
        url = env.get("IOTLINK_REAL_MASTER_URL", "").strip()
        if not url:
            raise ValueError("IOTLINK_REAL_MASTER_URL es obligatorio en modo real")
    else:
        url = env.get(
            "IOTLINK_SIMULATED_MASTER_URL",
            "http://iotlink-master:1880/api/v1/measurements",
        ).strip()

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("La URL debe incluir protocolo HTTP(S) y host")
    if parsed.username or parsed.password:
        raise ValueError("No incluyas credenciales en la URL")

    return {
        "mode": mode,
        "url": url,
        "token": env.get("IOTLINK_REAL_MASTER_TOKEN", "").strip() if mode == "real" else "",
        "interval": _positive("IOTLINK_POLL_INTERVAL_SECONDS", env.get("IOTLINK_POLL_INTERVAL_SECONDS", "5")),
        "timeout": _positive("IOTLINK_HTTP_TIMEOUT_SECONDS", env.get("IOTLINK_HTTP_TIMEOUT_SECONDS", "5")),
        "once": env.get("IOTLINK_RUN_ONCE", "false").strip().lower() in ("true", "1", "yes"),
    }


def validate_batch(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or payload.get("schema_version") != "1.0":
        raise ValueError("Contrato JSON incompatible. Se requiere schema_version 1.0")
    readings = payload.get("readings")
    if not isinstance(readings, list):
        raise ValueError("'readings' debe ser una lista")

    result = []
    for index, reading in enumerate(readings):
        if not isinstance(reading, dict):
            raise ValueError(f"Lectura {index}: se requiere un objeto")
        device_id = reading.get("device_id")
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError(f"Lectura {index}: device_id obligatorio")

        timestamp = reading.get("timestamp")
        if not isinstance(timestamp, str):
            raise ValueError(f"Lectura {index}: timestamp obligatorio")
        try:
            date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Lectura {index}: timestamp no válido") from exc
        if date.tzinfo is None or date.utcoffset() is None:
            raise ValueError(f"Lectura {index}: timestamp sin zona horaria")

        quality = reading.get("quality", "good")
        if quality not in ("good", "uncertain", "bad"):
            raise ValueError(f"Lectura {index}: calidad no válida")

        values = reading.get("values")
        if not isinstance(values, dict) or not values:
            raise ValueError(f"Lectura {index}: 'values' debe tener mediciones")
        for name, value in values.items():
            if not isinstance(name, str) or not name:
                raise ValueError(f"Lectura {index}: variable sin nombre")
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError(f"Lectura {index}: {name} debe ser un número finito")

        result.append({
            "device_id": device_id,
            "timestamp": timestamp,
            "quality": quality,
            "values": values,
        })
    return result


def read_master(configuration: dict[str, Any]) -> list[dict[str, Any]]:
    headers = {"Accept": "application/json"}
    if configuration["token"]:
        headers["Authorization"] = "Bearer " + configuration["token"]
    request = Request(configuration["url"], headers=headers, method="GET")
    with urlopen(request, timeout=configuration["timeout"]) as response:
        return validate_batch(json.load(response))


def log(level: str, event: str, **fields: Any) -> None:
    output = {
        "level": level,
        "event": event,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    print(json.dumps(output, ensure_ascii=False), file=sys.stderr if level == "error" else sys.stdout, flush=True)


def main() -> int:
    try:
        configuration = settings()
    except ValueError as exc:
        log("error", "invalid_configuration", message=str(exc))
        return 2

    log("info", "worker_started", mode=configuration["mode"], url=configuration["url"])
    while True:
        success = True
        try:
            readings = read_master(configuration)
            for reading in readings:
                log("info", "measurement", master_mode=configuration["mode"], **reading)
            if not readings:
                log("info", "empty_batch", master_mode=configuration["mode"])
        except (OSError, ValueError) as exc:
            success = False
            log("error", "acquisition_failed", mode=configuration["mode"], message=str(exc))

        if configuration["once"]:
            return 0 if success else 1
        time.sleep(configuration["interval"])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("info", "worker_stopped")
