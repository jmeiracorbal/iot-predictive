# iot-predictive

Laboratorio reproducible de IoT industrial. Este primer incremento simula la monitorización de **dos motores industriales**, con temperatura, vibración y revoluciones. Es independiente de cualquier startup o instalación real.

## Servicios

- `iotlink-master`: Node-RED con un flujo que simula una API HTTP de maestro industrial.
- `iotlink-worker`: Python independiente que consulta periódicamente al maestro, valida lecturas y emite registros JSON por consola.
- `compose.yaml`: arranca los dos contenedores. La fuente de datos se cambia por variables de entorno.

**No se emula el protocolo físico IO-Link.** Se simula la interfaz de salida de datos del maestro. Para conectarse a un maestro real debe exponer el mismo contrato HTTP, directamente o a través de un adaptador específico del fabricante.

## Arranque

Requisitos: Docker Compose v2, contenedores Linux, arquitectura AMD64 o ARM64.

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f iotlink-worker
```

Con la configuración por defecto, el worker recibe datos de dos motores cada cinco segundos. El segundo motor presenta una tendencia de incremento artificial de vibración para observar un escenario de fallo simulado. Estas curvas no representan un modelo físico validado.

Node-RED: http://127.0.0.1:1880

```bash
curl http://127.0.0.1:1880/health
curl http://127.0.0.1:1880/api/v1/measurements
docker compose logs --tail=30 iotlink-worker
```

La interfaz Node-RED no incluye autenticación en este laboratorio. Solo se publica en `127.0.0.1` por defecto y no debe exponerse públicamente.

## Alternar entre maestro simulado y real

En `.env`, cambiar:

```dotenv
IOTLINK_MASTER_MODE=real
IOTLINK_REAL_MASTER_URL=http://192.168.1.40/api/v1/measurements
IOTLINK_REAL_MASTER_TOKEN=
```

Ejecutar `docker compose up -d --build`. La URL real debe ser accesible desde **el contenedor**, no solo desde el host. En modo real el maestro simulado sigue arrancando, pero el worker no lo consulta.

Si el maestro real usa OPC UA, MQTT, una API propietaria, otra estructura JSON o autenticación diferente, necesitará un adaptador. No existe una interfaz IP universal para todos los maestros IO-Link.

Las credenciales no deben incorporarse al repositorio. `.env` está en `.gitignore`.

## Contrato de lectura

`GET /api/v1/measurements` devuelve:

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
      "values": { "temperature_c": 47.4, "vibration_mm_s": 2.1, "rpm": 1450 }
    }
  ]
}
```

Los tiempos deben llevar zona horaria. La calidad puede ser `good`, `uncertain` o `bad`. Se admiten otras variables numéricas, conservando el esquema. Por ahora el worker solo lee, valida y escribe una línea JSON por lectura. **No hay todavía PostgreSQL, Jupyter ni predicción**, que pertenecerán a fases posteriores.

## Código fuente

```text
iot-predictive/
├── compose.yaml
├── .env.example
├── iotlink/
│   ├── master/
│   │   ├── Dockerfile
│   │   └── flows.json
│   └── worker/
│       ├── Dockerfile
│       ├── worker.py
│       └── tests/test_worker.py
└── .github/workflows/ci.yaml
```

El flujo Node-RED está incorporado a la imagen. Los cambios hechos en su editor no persistirán tras recrear el contenedor. Para conservarlos, exporta el flujo a `iotlink/master/flows.json` y reconstruye la imagen.

## Pruebas

```bash
python -m unittest discover -s iotlink/worker/tests -v
python -m json.tool iotlink/master/flows.json > /dev/null
docker compose --env-file .env.example config --quiet
```

El workflow de CI ejecuta pruebas unitarias y validaciones de configuración. El despliegue con Docker debe comprobarse en un entorno con Docker. Este laboratorio no envía órdenes a equipos físicos.
