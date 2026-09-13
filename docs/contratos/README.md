# Contrato de integración v1

Entrada publica **`SolicitudDePartnerListaParaAtencion.v1`**, un hecho posterior a la evaluación y transición confirmadas. Las solicitudes rechazadas no producen este evento. No es una orden para cotizar ni confirma que exista un Trabajo.

- Tópico: `persistent://public/default/solicitud-partner-lista-v1`.
- Serialización: Avro binario, con esquema registrado en Pulsar.
- [Esquema exportado](solicitud-lista-v1.avsc) y [ejemplo JSON equivalente](solicitud-lista-v1.ejemplo.json). El JSON ilustra el contenido; no es el formato enviado.
- Productor: Entrada de Solicitudes de Partner. Los consumidores solo necesitan este contrato; no importan clases ni consultan tablas del productor.

| Campos | Significado |
|---|---|
| `event_id` | UUID original del evento. Clave de idempotencia externa; se conserva al reintentar. |
| `tipo`, `version_contrato` | `SolicitudDePartnerListaParaAtencion.v1`, `1`. |
| `instante` | Instante original del hecho, ISO 8601 UTC; no es la hora de reenvío. |
| `correlacion`, `id_solicitud` | UUID de la solicitud. La clave de partición del mensaje también es este UUID. |
| `version_solicitud` | Versión del agregado al quedar listo: `2` en este flujo. |
| `id_partner`, `referencia_externa`, `categoria` | Identidad del partner y datos de recepción. |
| `tipo_solicitud` | `SINIESTRO` o `INSTALACION`. |
| `aprobacion_previa` | Booleano o `null`. Ausencia y aprobación negativa son valores diferentes. |
| `tipo_red` | `GENERAL_HDA` o `HOMOLOGADA_PARTNER`. |
| `id_politica`, `version_politica` | Política utilizada en la evaluación inicial. |

Cada servicio usa una suscripción distinta. Sus réplicas comparten la suscripción y pueden usar `Shared`; no se garantiza orden global. Las suscripciones de laboratorio son `atencion` y `estadisticas`. Pueden añadirse otras con `scripts/preparar_pulsar.py --suscripciones cotizaciones` sin modificar el productor. Este comando crea suscripciones durables antes del envío y no reinicia cursores existentes.

La entrega es al menos una vez. El consumidor persiste su efecto y la identidad del evento en una transacción antes del ACK. Un timeout de envío no prueba que el broker no recibió el evento: una reentrega puede tener otro MessageId y el mismo `event_id`. El ejemplo `scripts/consumir_eventos.py` persiste en SQLite, detecta contenido contradictorio y confirma después del commit. Cada consumidor conserva su propia base. El límite predeterminado es un mensaje y la espera máxima por mensaje es 15 segundos; `--limite` permite recibir más.

## Preparación local repetible

Ejecutar desde la raíz del servicio, después de `uv sync --locked`:

```bash
docker compose up -d --wait
uv run --locked python scripts/preparar_pulsar.py
docker compose exec -T pulsar bin/pulsar-admin topics set-backlog-quota persistent://public/default/solicitud-partner-lista-v1 --limit 50M --policy producer_exception
docker compose exec -T pulsar bin/pulsar-admin topics set-backlog-quota persistent://public/default/solicitud-partner-lista-v1 --type message_age --limitTime 30m --policy producer_exception
docker compose exec -T pulsar bin/pulsar-admin topics set-retention persistent://public/default/solicitud-partner-lista-v1 --time 1h --size 100M
docker compose exec -T pulsar bin/pulsar-admin topics get-retention persistent://public/default/solicitud-partner-lista-v1
```

La retención configurada es 60 minutos/100 MiB para mensajes confirmados. Las suscripciones durables conservan sus pendientes; al alcanzar backlog de 50 MiB o 30 minutos se rechazan nuevas publicaciones hasta recuperar el consumidor, conservando la salida en el outbox. No se configura expulsión de mensajes. Esta ventana basta para el ensayo local, no acredita retención ilimitada. Preparar las suscripciones antes de publicar evita depender solo de retención para consumidores detenidos.

El Compose anuncia `127.0.0.1`, por lo que sus clientes se ejecutan en el host. Para infraestructura compartida hay que anunciar una dirección accesible desde sus clientes y establecer `PARTNER_PULSAR_URL` y `PARTNER_PULSAR_TOPIC`. No cambiar el tópico durante una recuperación pendiente. La política anterior se aplica al tópico local predeterminado; si se cambia, ajustar también los comandos administrativos.

Python 3.12.3, `pulsar-client[avro]` 3.13.0, fastavro 1.12.2 y broker 4.1.3 fueron probados juntos. `send()` espera confirmación del broker; el despacho externo se ejecuta separado del registro y del bus interno. La POC demuestra distribución y recuperación; recibir este evento no demuestra cotización, orquestación completa ni scoring de proveedores.
