# 06 — CQRS obligatorio y API

Estado: implementado y verificado localmente. Dependencia: 05. [Evidencia de cierre](evidencia-06-cqrs-api.md).

Alcance simplificado acordado tras la [auditoría](auditoria-06-cqrs-api.md): POC local con datos nuevos, API y proyector dentro del mismo proceso. No requiere conservar datos de incrementos anteriores.

Implementación concreta: `/solicitudes` para POST, GET por ID y listado; `lectura.solicitudes` con migración 0003; contrato `SolicitudDePartnerActualizada.v1` y destino `cqrs.solicitud.v1`. El `lifespan` de FastAPI administra despacho interno, publicadores y proyección mediante `config/procesamiento.py`. La suscripción CQRS se prepara automáticamente antes de publicar en su tópico. [Contrato y OpenAPI](../contratos/lectura.md).

## Objetivo

Separar escritura y lectura con una proyección persistente asíncrona dentro del módulo Solicitudes, consultable mediante FastAPI.

## Trabajo

1. Definir DTO de consulta con ID, partner, referencia, estado, resultado, motivo de rechazo o tipo de red determinado e identidad/versión de política cuando existan, fechas y versión aplicada. Una solicitud rechazada muestra su motivo sin red y una lista muestra red sin motivo de rechazo. Una solicitud recibida aún no tiene red determinada; no usar red general como valor por defecto. No representar datos aún pendientes como valores finales.
2. Implementar repositorio de lectura SQLAlchemy que consulte únicamente la vista del esquema `lectura`. Query handlers no dependen del repositorio de agregados ni del evaluador. Crear la vista mediante una migración; no releer el estado mutable de escritura para resolver consultas.
3. Conservar el proyector como componente con suscripción propia estable, ejecutado en un hilo del mismo proceso FastAPI. Alimentarlo por Pulsar con los tres hechos de Solicitudes según la tabla siguiente, usando contrato, mapeador y destino CQRS independientes del contrato público. Reutilizar outbox y despachador con filtro propio; centralizar rutas en `config/rutas.py`. Solicitudes y Reglas siguen comunicándose por el bus interno. Preparar la suscripción CQRS desde lifespan antes de publicar los primeros mensajes de lectura, partiendo de una base de laboratorio limpia. No implementar carga histórica ni republicación de eventos anteriores.
4. Reutilizar los datos completos de los eventos actuales: registro v1 y estado final v2. Deduplicar por consumidor e ID y actualizar vista en una sola transacción; ACK después del commit. Aplicar únicamente versiones superiores mediante actualización atómica para impedir retrocesos incluso ante carreras. Un evento final v2 puede crear la vista sin haber recibido v1; v1 posterior no la modifica. Para igual versión, aceptar contenido equivalente y señalar contradicciones sin confirmarlas como éxito. No implementar un mecanismo genérico de recuperación de huecos ni soporte para versiones futuras.
5. Exponer POST de registro, GET por ID y listado por partner paginado en una misma API, con dependencias diferenciadas de comando y consulta. El POST confirma recepción durable con ID y `Location`; no espera a que Reglas o la proyección terminen. Registro nuevo y reintento idéntico devuelven `202` con el mismo ID; conflicto de contenido devuelve `409` y datos inválidos `422`. Un fallo de persistencia no devuelve confirmación de recepción. Conservar la comparación de datos del handler existente.
6. GET devuelve `200` cuando existe una vista del partner seleccionado. Si no está disponible, devuelve `404` con mensaje «no disponible en la vista»; documentar que puede ser retraso de proyección y que el cliente con registro confirmado puede reintentar. No afirmar inexistencia en escritura ni consultar el agregado para resolver esa ausencia. Listado con orden determinista, desempate por ID y límite de página acotado.
7. Usar una identidad de partner de laboratorio explícita mediante un adaptador sustituible en pruebas. El registro utiliza esa identidad y las consultas filtran por ella dentro del repositorio, tanto por ID como en listado. Documentar cómo seleccionarla para la demostración y comprobar que no se mezclan datos de dos partners. Esto demuestra filtrado funcional, no autenticación ni seguridad de producción; no construir una plataforma de identidad para cerrar 06.
8. Mantener separados modelo y repositorio de lectura respecto de escritura. Se permite compartir servidor PostgreSQL, credencial y factoría de conexiones en esta POC; cada operación conserva su propia sesión/transacción. No exigir tres roles de base, pruebas de permisos ni despliegue independiente de la API de consultas. El proyector puede reutilizar el inbox existente con identidad de consumidor propia, conservando la transacción conjunta con la vista.
9. Documentar OpenAPI, consistencia eventual y límites. Documentar un único comando de arranque de FastAPI; lifespan inicia los cuatro bucles y los detiene antes de cerrar la base. No iniciar ciclos al importar módulos ni bloquear el event loop HTTP con operaciones de Pulsar o SQL.

## Rutas y organización

| Evento de dominio | Destinos durables |
|---|---|
| `SolicitudPartnerRegistrada` | Bus interno hacia Reglas y publicación CQRS. |
| `ReglasDePartnerEvaluadas` | Bus interno hacia Solicitudes; no necesita alimentar la vista directamente. |
| `SolicitudPartnerListaParaAtencion` | Integración pública existente y publicación CQRS. |
| `SolicitudPartnerRechazada` | Publicación CQRS; no emite el contrato público de solicitud lista. |

Los tres hechos destinados a CQRS alimentan un tópico de lectura con su contrato propio y una suscripción estable del proyector. Definir sus nombres en configuración sin reutilizar el tópico público de solicitud lista. Una caída de Pulsar conserva las salidas pendientes y no impide registrar ni evaluar por el bus interno.

| Ubicación dentro del servicio | Responsabilidad |
|---|---|
| Aplicación de Solicitudes | DTO, puerto de lectura y handlers de consulta. |
| Infraestructura de Solicitudes | Repositorio/vista de lectura, proyección y adaptadores/esquemas Pulsar de CQRS. Mantener separados mapeos SQL y Pulsar. |
| `api/` | Endpoints, traducción HTTP y dependencia de identidad de laboratorio. |
| `config/bootstrap.py` y `config/rutas.py` | Composición y rutas centralizadas. |
| `config/procesamiento.py` y `seedwork/infraestructura/ciclos.py` | Ciclo de vida de los bucles dentro de FastAPI y ejecución en hilos. |
| `migraciones/` | Estructura persistente del modelo de lectura. |

SQL permanece encapsulado en repositorios; no añadir consultas directas a endpoints, handlers, bootstrap o ciclos de procesamiento. Conservar los dos módulos y el seedwork local.

## Pruebas

Unitarias: query solo usa repositorio de lectura; comandos solo escriben por UoW. API con dependencias falsas: registro, consulta de rechazo con motivo, siniestro sin campo de aprobación (error de validación) frente a aprobación falsa (recepción válida y rechazo posterior), reintento incluso después de evaluación, conflicto, validación, ausencia temporal de vista, paginación y filtrado con dos partners. Mantener liveness y pruebas unitarias sin red.

Integración con PostgreSQL y Pulsar: iniciar desde una base de laboratorio limpia y recorrer POST HTTP → escritura/outbox → bus interno → publicación CQRS → proyector → GET/listado. Verificar recibida, lista y rechazada; una política ausente conserva la recepción y permite continuar tras corregir la configuración. Reiniciar el servicio completo con solicitudes pendientes y la misma suscripción; recuperar la evaluación y la vista sin borrar datos. Las pruebas de componentes pueden detener únicamente la proyección para verificar retrasos, sin requerir despliegues separados.

Probar v2 antes de v1, reentrega, contenido contradictorio y carrera v1/v2 sin regresión de estado. Fallar antes del commit revierte vista e inbox; caer después del commit y antes del ACK no duplica efectos. Verificar entrega recuperable de las nuevas salidas CQRS y que el rechazo nunca se publique como solicitud lista. Registrar latencia de proyección como evidencia local, sin exigir un experimento de escalabilidad. Postman es un complemento opcional.

## Cierre

Registrar por HTTP, proyectar los tres estados, consultar exclusivamente la vista y demostrar recuperación sin duplicados ni retrocesos. Las queries no modifican dominio. Ejecutar la suite completa y actualizar README con comandos y evidencia real.

Fuera de alcance: migración de datos de incrementos anteriores, carga histórica, plataforma de replay, autenticación de producción, roles PostgreSQL separados y despliegue independiente de consultas. No eliminar el archivo durable existente de 05. Arranque limpio aplica a la preparación del laboratorio, nunca a la recuperación tras una caída. La campaña de carga y los experimentos con otros consumidores permanecen en 07; compartir motor físico no demuestra aislamiento de recursos ni escalamiento independiente de bases.

## Simplificación de organización

Las conversiones de persistencia se agrupan en `mapeadores.py`; los contratos Avro públicos y de lectura, en `mapeadores_eventos.py`; los repositorios de escritura, consulta y actualización de la vista, en `repositorios.py`. Se conservan clases separadas porque las consultas abren su sesión y la actualización participa en la transacción del proyector. `proyecciones.py` mantiene la coordinación de inbox y vista. Las funciones `componer_*` y `crear_uow_*` existentes son las fábricas explícitas; no se introduce una fábrica genérica adicional.
