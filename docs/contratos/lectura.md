# Contrato de lectura CQRS v1

`SolicitudDePartnerActualizada.v1` alimenta únicamente la vista de Solicitudes. No sustituye al evento público `SolicitudDePartnerListaParaAtencion.v1`.

- Esquema Avro: [solicitud-lectura-v1.avsc](solicitud-lectura-v1.avsc).
- Ejemplo de recepción: [solicitud-lectura-v1.ejemplo.json](solicitud-lectura-v1.ejemplo.json).
- Contrato HTTP: [openapi.json](openapi.json), también disponible en `/openapi.json` y `/docs` al iniciar la API.
- Tópico predeterminado: `persistent://public/default/solicitud-partner-lectura-v1`.
- Suscripción durable: `solicitudes-lectura-v1`; preparar antes de registrar datos.
- Destino outbox: `cqrs.solicitud.v1`. Registro y cada estado final generan una entrega hacia él. La evaluación de Reglas conserva su ruta interna.

`event_id` conserva el ID del evento de dominio; la clave de partición es `id_solicitud`. El tipo de mensaje y `version_contrato=1` identifican el formato. `version_solicitud` indica el estado de la solicitud; `version_politica` identifica la política aplicada. Los reintentos conservan identidad y contenido.

| Estado | Versión de solicitud | Resultado y condiciones |
|---|---|---|
| `RECIBIDA` | 1 | Resultado, motivo, red y política nulos. |
| `LISTA_PARA_ATENCION` | 2 | `ADMISIBLE`, red general u homologada, identidad/versión de política; motivo nulo. |
| `RECHAZADA` | 2 | `NO_ADMISIBLE`, motivo de rechazo y política; red nula. |

Cada mensaje contiene ID, partner, referencia, categoría, tipo de solicitud y fechas suficientes para crear la vista sin consultar el agregado. V2 puede llegar primero: crea la vista completa. V1 posterior no hace retroceder el estado. Una actualización de la misma versión debe tener contenido equivalente; una contradicción conserva el mensaje sin confirmar éxito.

El consumidor confirma vista e inbox juntos y luego hace ACK. Un fallo temporal o mensaje inválido genera NACK y diagnóstico; la entrega se vuelve a intentar. No hay descarte silencioso ni plataforma propia de cuarentena. Una caída posterior al commit puede causar reentrega: la deduplicación conserva un solo efecto. Las réplicas que procesen esta vista deben compartir suscripción e identidad de consumidor; no se ensayó escalabilidad en 06.

La POC comienza con datos nuevos. No existe carga histórica de registros anteriores al despliegue de CQRS. Reiniciar después de una caída conserva la misma base, tópico y suscripción; no se reinicializan para recuperar.
