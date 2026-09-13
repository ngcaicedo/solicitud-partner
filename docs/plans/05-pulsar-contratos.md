# 05 — Bus interno, Pulsar y contrato público

Estado: implementado y verificado localmente. Dependencia: 04. [Evidencia de cierre](evidencia-05-pulsar-contratos.md).

Implementación concreta: archivo transaccional `mensajeria.eventos`, entrega síncrona por `BusEventosLocal.entregar`, ciclos independientes en `workers/despacho.py` y publicador Avro v1. [Contrato y comandos](../contratos/README.md).

## Objetivo

Automatizar el flujo Solicitudes → Reglas → Solicitudes mediante el bus interno y publicar un evento de integración por Pulsar para consumidores externos independientes. Conservar recepción durable, tres UoW e idempotencia, sin exigir el ciclo completo de un Trabajo para demostrar la POC.

## Arquitectura y contrato

| Hecho | Transporte y destino |
|---|---|
| `SolicitudPartnerRegistrada` | Bus interno → handler de Reglas. |
| `ReglasDePartnerEvaluadas` | Bus interno → handler de Solicitudes, que traduce a sus tipos propios. |
| `SolicitudPartnerListaParaAtencion` | Adaptador de integración → `SolicitudDePartnerListaParaAtencion.v1` → Pulsar. |
| `SolicitudPartnerRechazada` | Estado y evento durables locales, con motivo; no emite solicitud lista. |

El contrato público es un **evento**, no un comando: informa que la solicitud ya fue evaluada y quedó lista. Se conserva ese nombre y significado; la etiqueta `SolicitudRegistrada` de las diapositivas no lo reemplaza ni adelanta su emisión a la recepción inicial.

Entrada define el esquema v1, campos, tópico y ejemplos en este repositorio. Los consumidores externos implementan ese contrato sin importar nuestras clases o tablas; no se requiere su aprobación previa para cerrar 05. Varios consumidores pueden recibir el mismo evento mediante suscripciones independientes. Las réplicas de un consumidor comparten su suscripción.

La POC permite conectar Orquestación/Atención, Cotizaciones y un nuevo consumidor de estadísticas o Scoring según el efecto que implementen. Recibir solicitudes demuestra consumo/proyección sobre solicitudes; no demuestra por sí solo cotización completa, cierre del Trabajo ni puntuación de proveedores. El plan 07 separa esos resultados de los escenarios empresariales originales. No es requisito construir la cadena Orquestación → Cotizaciones → cierre → Scoring en este incremento.

## Trabajo

1. Conservar los handlers, eventos de dominio, inbox y tres UoW de 04. Reutilizar `config/bootstrap.py` y el bus local para conectar Solicitudes con Reglas; no crear consumidores Pulsar ni esquemas Avro para esos dos intercambios internos.
2. Sustituir `destinos_laboratorio` por destinos explícitos de entrega interna e integración. Reutilizar el outbox y sus marcas por destino. Inspeccionar pendientes de laboratorio antes del cambio y documentar su resolución si existen. No construir un motor genérico de rutas.
3. Automatizar el despacho interno mediante una función de ejecución síncrona iniciada desde `workers/despacho.py`, que recupera salidas persistidas y las entrega al bus. El éxito de la entrega exige que el handler destinatario termine su UoW, o reconozca un duplicado ya confirmado. `BusEventosLocal.publicar()` solo encola: no permite marcar la salida como completada. Adaptar mínimamente la conexión entre bus y despachador para asociar el resultado con su entrega. Si no hay handler registrado para una ruta interna requerida, conservar pendiente y señalar error.
4. Tras caída, reconstruir las entregas desde PostgreSQL; la cola en memoria no es la fuente durable. Probar especialmente commit del handler seguido de caída antes de marcar la entrega. El inbox evita repetir el efecto al reintentar. Mantener las reservas y tokens existentes, publicación secuencial, lotes pequeños y plazos coherentes; sin renovación de reservas ni concurrencia avanzada.
5. Definir el esquema Avro v1 y mapeador del evento público en infraestructura de Solicitudes. Conservar ID del evento, instante original, ID de solicitud, tipo, versión, partner y condición de red general/homologada, además de los datos de solicitud incluidos en el contrato. Usar ID de solicitud para correlación. Mantener identidad y contenido equivalentes en reintentos; MessageId del broker no sustituye al ID del evento. No añadir campos ficticios para aparentar un Trabajo completo.
6. Incorporar el cliente Pulsar con uv y registrar versiones verificadas de Python, cliente y broker. Implementar el adaptador `Publicador` y el relay de integración reutilizando el outbox. Marcar enviado solo tras confirmación positiva del broker; fallar el envío no revierte la solicitud ni su evaluación. Los handlers no publican directamente a Pulsar.
7. Separar el avance interno de la disponibilidad del broker: una caída de Pulsar permite registrar, evaluar y dejar lista o rechazada la solicitud; solo la entrega externa queda pendiente. Definir en `workers/despacho.py` funciones de arranque y parada del despacho interno y de la publicación externa. Estas funciones conectan y ejecutan repetidamente los despachadores existentes, con apertura/cierre de recursos, pausas y diagnóstico sencillo. Mantener ambas actividades independientes para que la espera de Pulsar no bloquee el despacho interno. No iniciar ciclos al importar el módulo; su ejecución debe ser explícita. No compartir una Session entre ejecuciones.
8. Preparar standalone local y conexión configurable al broker compartido. Documentar tópico público, suscripciones de prueba distintas y conservación de mensajes para la recuperación ensayada. Un envío al tópico sirve a varios suscriptores; no crear una fila outbox por consumidor externo. Cada servicio conserva su implementación; no crear los repositorios de los compañeros ni CI remota.
9. Mantener los eventos completos de registro y estados finales disponibles para CQRS. En 06 se concreta su entrega al proyector sin depender únicamente del evento público de solicitud lista: una recibida y una rechazada también deben proyectarse. En 05 no descartar sus documentos persistidos ni fingir una entrega a un proyector inexistente.

## Errores y confirmaciones

| Situación | Comportamiento mínimo |
|---|---|
| Evaluación negativa por aprobación previa falsa | Resultado empresarial válido; confirmar evaluación, entregar internamente y conservar el rechazo. |
| Duplicado interno equivalente | Reconocer el efecto confirmado y completar la entrega sin repetirlo. |
| Fallo temporal del handler o política ausente | Mantener recepción y entrega pendiente; reintentar tras demora/corrección. No inventar rechazo empresarial. |
| Documento inválido o contenido contradictorio | Diagnóstico y conservación de la entrega; detener ese procesamiento para intervención si es necesario. |
| Fallo de Pulsar | Mantener salida de integración pendiente y error visible; el flujo interno continúa. |
| Consumidor externo de prueba | Persistir efecto e inbox antes del ACK; ante error, no confirmar éxito. |

El bus interno no usa ACK de Pulsar. Su confirmación es el éxito durable del handler destinatario. La copia del evento guardada para auditoría/futura lectura no debe confundirse con una entrega pendiente a un consumidor activo. Se permite intervención manual ante mensajes inválidos; no se construye plataforma de cuarentena o replay.

## Organización de archivos

Rutas relativas a `src/solicitudes_partner/`; reutilizar archivos existentes cuando corresponda.

| Ubicación | Responsabilidad |
|---|---|
| `seedwork/infraestructura/bus_eventos_local.py` y `despacho_outbox.py` | Entrega interna y resultado asociado a la salida persistida; conservar el mecanismo común de reservas. |
| `seedwork/infraestructura/publicador_pulsar.py` | Adaptador de publicación externa. |
| `modulos/solicitudes/infraestructura/esquemas/v1/` y `mapeador_integracion.py` | Contrato público y conversión; distinguir mapeos de integración y SQL. |
| `config/rutas.py`, `config/persistencia.py` y `config/settings.py` | Rutas internas/externas y parámetros. |
| `config/bootstrap.py` | Composición de handlers, adaptadores y despachadores. |
| `workers/despacho.py` | Ciclos, arranque/parada, señales y cierre de recursos. |
| `seedwork/infraestructura/reloj.py` e `identificadores.py` | Implementaciones únicas de los puertos de reloj e identificadores. |

Ajuste acordado tras revisar la implementación: separar la ejecución continua en `workers/despacho.py`, manteniendo `config/bootstrap.py` dedicado a composición. El worker ejecuta los despachadores existentes; sus reglas de entrega permanecen en infraestructura.

Los consumidores externos de laboratorio viven en las pruebas/herramientas de demostración, no como módulos empresariales nuevos. Documentar comandos y variables al implementar. No agregar fachadas de reexportación, otro bus ni comandos intermedios sin responsabilidad adicional.

## Pruebas y cierre

- Unitarias sin red: rutas, conversiones v1, identidad estable, condiciones de red y rechazo sin evento público de solicitud lista.
- PostgreSQL: iniciar despacho automático y registrar mediante handler/script; comprobar evaluación y transición sin avance manual del bus por la prueba. Encolar sin ejecutar, fallar el handler o carecer de suscriptor no marca la entrega como completada.
- Reiniciar después del commit interno y antes de marcar su salida: un único efecto, con recepción conservada. No depender de la cola volátil para recuperar.
- PostgreSQL y Pulsar: detener broker, registrar y evaluar; verificar estado final local y salida externa pendiente. Reiniciar y recibir el evento público.
- Caer después de publicar y antes de marcar: republicación con el mismo ID y efecto externo idempotente. Caer en el consumidor de prueba después del commit y antes del ACK tampoco duplica su efecto.
- Dos suscripciones externas independientes reciben el mismo evento y persisten su recepción. Detener una no impide que la otra avance; al reiniciar recupera sus pendientes. Estos consumidores son dobles de laboratorio, no acreditan microservicios empresariales terminados.
- Registrar versiones, comandos, errores y resultados persistentes; ejecutar verificaciones locales y empaquetado. Los logs solos no demuestran procesamiento.

## Límites y trabajo posterior

**06:** API y CQRS, incluida proyección de recibidas y rechazadas. El transporte del proyector es una decisión de su ejecución separada; no cambia el bus entre Solicitudes y Reglas.

**07:** POC de consumidores independientes, recuperación, extensibilidad y carga. Documentar el efecto real de cada consumidor y la cobertura parcial respecto de E3/E4/E8 originales cuando corresponda. No exigir el ciclo empresarial completo ni presentarlo como implementado.

**08:** despliegue compartido y clúster requerido por la rúbrica; standalone acredita laboratorio local.

Cadena completa de causalidad, compatibilidad histórica del adaptador, renovación de reservas y plataforma propia de cuarentena/replay no son criterios de cierre de 05.
