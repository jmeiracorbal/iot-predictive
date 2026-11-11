# iot-predictive

A Docker Compose example for simulated industrial motor telemetry.

## Services

- `iotlink-worker` continuously generates measurements for two motors and publishes them via HTTP.
- `iotlink-master` runs Node-RED. It receives measurements and exposes the latest reading from each motor.

The example simulates the network-facing interface of an industrial master, not the physical IO-Link protocol.

## Start

Requires Docker Compose v2 and Linux containers.

```sh
cp .env.example .env
docker compose up --build -d
docker compose logs -f iotlink-worker
```

Node-RED editor: `http://127.0.0.1:1880`

Check the API:

```sh
curl http://127.0.0.1:1880/health
curl http://127.0.0.1:1880/api/v1/measurements
```

### HTTP API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/measurements` | Receive a batch of measurements. Returns `202` and the accepted count. |
| `GET` | `/api/v1/measurements` | Return the latest reading per device. Returns an empty list before the first batch. |
| `GET` | `/health` | Return `{"status":"ok"}`. |

Each batch contains a `schema_version` (`1.0`) and `readings`. A reading includes `device_id`, a timezone-aware `timestamp`, `quality`, and numeric `values`. Invalid batches receive `400`.

Example POST:

```sh
curl -i -X POST http://127.0.0.1:1880/api/v1/measurements \
  -H 'Content-Type: application/json' \
  -d '{"schema_version":"1.0","readings":[{"device_id":"motor-03","timestamp":"2026-11-11T10:00:00Z","quality":"good","values":{"temperature_c":45.2,"vibration_mm_s":1.8,"rpm":1460}}]}'
```

Readings are held in Node-RED's in-memory context and are replaced by newer readings from the same device. They do not survive a container restart. If delivery fails, the worker logs the error and continues generating measurements. Failed batches are not queued.

## Configuration

`cp .env.example .env` provides a complete simulated setup. Every Compose interpolation uses a required environment value without a fallback.

| Variable | Description |
| --- | --- |
| `IOTLINK_BIND_ADDRESS` | Host interface to publish Node-RED on |
| `IOTLINK_MASTER_PORT` | Node-RED's listening and published port |
| `IOTLINK_MASTER_URL` | Worker destination URL |
| `IOTLINK_GENERATION_INTERVAL_SECONDS` | Seconds between generated batches |
| `IOTLINK_HTTP_TIMEOUT_SECONDS` | Publish request timeout in seconds |
| `IOTLINK_RUN_ONCE` | Generate and publish one batch, then exit (`true` or `false`) |

To use a compatible external master or gateway, update `IOTLINK_MASTER_URL` to its HTTP ingestion endpoint, reachable from the worker's network. That endpoint must accept this batch format. Vendor-specific IO-Link protocols are not implemented. Do not send simulated measurements to production equipment.

The Node-RED editor and the ingestion API have no authentication and are bound to `127.0.0.1` on the host by the example configuration. Keep the environment on a trusted network.

## Tests

```sh
python -m unittest discover -s tests -v
python -m json.tool iotlink/master/flows.json > /dev/null
docker compose --env-file .env.example config --quiet
```
