# iot-predictive

Industrial data acquisition example using Docker Compose. The sample monitors two simulated electric motors and reports temperature, vibration and RPM.

## Services

- `iotlink-master`: Node-RED with an HTTP endpoint returning simulated measurements.
- `iotlink-worker`: Python service that polls the endpoint, validates its JSON response and logs the readings.

Node-RED simulates the master's network-facing API, not the physical IO-Link protocol.

## Run

Requires Docker Compose v2 and Linux containers.

```sh
cp .env.example .env
docker compose up --build -d
docker compose logs -f iotlink-worker
```

Node-RED editor: http://127.0.0.1:1880

```sh
curl http://127.0.0.1:1880/health
curl http://127.0.0.1:1880/api/v1/measurements
```

The example returns measurements for two motors. The second motor's vibration increases over time. The simulator is not a calibrated physical model.

The Node-RED editor has no authentication. `.env.example` binds it to localhost. Do not expose it to an untrusted network.

## Configuration

Copy `.env.example` to `.env` before starting the stack. Compose reads all interpolated values from the environment and supplies no fallback values.

| Variable | Description |
| --- | --- |
| `IOTLINK_MASTER_MODE` | `simulated` or `real` |
| `IOTLINK_MASTER_URL` | HTTP measurement endpoint reachable from the worker |
| `IOTLINK_BIND_ADDRESS` | Host interface for the Node-RED port |
| `IOTLINK_MASTER_PORT` | Published host port for Node-RED |
| `IOTLINK_POLL_INTERVAL_SECONDS` | Seconds between requests |
| `IOTLINK_HTTP_TIMEOUT_SECONDS` | HTTP request timeout in seconds |
| `IOTLINK_RUN_ONCE` | `true` to poll once, otherwise `false` |

`.env.example` contains a complete working configuration for the simulated master.

To read from a real master, set `IOTLINK_MASTER_MODE=real` and change `IOTLINK_MASTER_URL` to an address accessible from the worker container. The simulated master still starts but is not queried by the worker. The external device must serve the same HTTP JSON contract, either directly or through an adapter. Vendor protocols are not implemented.

## HTTP contract

`GET /api/v1/measurements` returns:

```json
{
  "schema_version": "1.0",
  "source": "iotlink-master-simulated",
  "generated_at": "2026-11-10T10:00:00Z",
  "readings": [
    {
      "device_id": "motor-01",
      "timestamp": "2026-11-10T10:00:00Z",
      "quality": "good",
      "values": {
        "temperature_c": 47.4,
        "vibration_mm_s": 2.1,
        "rpm": 1450
      }
    }
  ]
}
```

Timestamps must have a timezone. `quality` is one of `good`, `uncertain` or `bad`. The worker rejects malformed payloads and writes one JSON log per reading.

## Tests

```sh
python -m unittest discover -s iotlink/worker/tests -v
python -m json.tool iotlink/master/flows.json > /dev/null
docker compose --env-file .env.example config --quiet
```

GitHub Actions runs the tests and checks. The Compose stack must be run separately to verify container startup. This phase does not implement SQL storage, model training or device control.
