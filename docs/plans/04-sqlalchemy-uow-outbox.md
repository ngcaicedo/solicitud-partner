# 04 — SQLAlchemy, PostgreSQL y entrega durable

Estado: implementado y verificado localmente. Dependencia: 03. [Evidencia de ejecución](evidencia-04-sqlalchemy-uow-outbox.md).

## Objetivo

Implementar la persistencia de Solicitudes y Reglas con SQLAlchemy y PostgreSQL, manteniendo tres unidades de trabajo independientes. Cada paso confirma sus datos y sus eventos de salida juntos; los consumidores confirman además su entrada procesada en esa misma transacción. Conservar identidad, trazabilidad e idempotencia al reiniciar y ante ejecuciones concurrentes.

Este plan incorpora H1–H6 de la [auditoría](auditoria-04-sqlalchemy-uow-outbox.md). Actualizar el documento no significa que sus garantías estén implementadas.

## Alcance y fronteras

04 implementa migraciones, repositorios, UoW SQL, inbox, serialización durable y reclamación/confirmación del outbox. Se comprueba con PostgreSQL real y un puerto de publicación falso, avanzando explícitamente las entregas en las pruebas.

05 automatiza la entrega durable hacia el bus interno y conecta el relay de integración a Pulsar, con contrato público definido por Entrada y pruebas de recuperación. El bus local sigue siendo el mecanismo de despacho en memoria; PostgreSQL conserva las entregas y el despachador verifica el éxito durable del handler. 06 conecta el registro HTTP y la proyección CQRS. No publicar directamente desde los handlers ni introducir Event Sourcing.

## Trabajo

1. Preparar PostgreSQL de desarrollo reproducible con volumen, comprobación de disponibilidad y credenciales de ejemplo. Reutilizar psycopg, Engine y sessionmaker de 01; incorporar Alembic al entorno bloqueado. Verificar documentación vigente al implementar cada integración. No conectar ni crear tablas durante imports.
2. Crear ORM y mapeadores por módulo, separados de entidades y objetos valor del dominio. Conservar todos los datos de solicitud, la evaluación original y su registro de origen. Solicitudes reconstruye su `ResultadoEvaluacion` propio; Reglas conserva su entidad y su evento. No recalcular políticas ni regenerar eventos al leer. **H2**.
3. Crear migraciones desde base vacía: tablas propietarias, claves, índices y restricciones. Unicidad de recepción por `(id_partner, referencia_externa)`, de evaluación inicial por `id_solicitud`, de origen asociado y de inbox por `(nombre_consumidor, id_evento)`. Preparar un esquema de lectura separado, sin implementar todavía vistas CQRS. **H3**.
4. Implementar UoW SQL con sesión nueva por ejecución, inicio, flush, commit, rollback y cierre explícitos. Cada repositorio utiliza la sesión de su UoW y no confirma por su cuenta. Los handlers conservan la responsabilidad del commit. La confirmación de registro nuevo solo se devuelve después del commit efectivo; el reintento equivalente devuelve la identidad ya confirmada. **H1**.
5. Extender el puerto común y los dobles para preparar entradas procesadas dentro de la UoW. Adaptar los dos handlers consumidores según la sección transaccional: inbox, evaluación/transición y outbox usan una única sesión. Ajustar retornos sin cambios y probar recuperación tras fallos. **H1**.
6. Respaldar las comprobaciones de negocio con restricciones y actualización condicionada por la versión leída. Conservar la versión original en el repositorio y comprobar que se actualizó una fila; una escritura obsoleta falla y revierte también sus salidas. Tras una colisión conocida, rollback y nueva lectura distinguen repetición de conflicto. Probar carreras en registro, evaluación y transición. **H3**.
7. Serializar los cuatro eventos mediante formatos explícitos y versionados, sin SDK ni serialización de objetos Python con pickle. Validar y persistir la salida en la misma transacción del efecto. Implementar decodificación desde almacenamiento, conservando identidad e instante originales. **H5**.
8. Implementar operaciones SQL de reclamación de lotes, vencimiento recuperable, finalización y reprogramación del outbox. Cada reserva tiene token propio; todas las actualizaciones comprueban su vigencia. Ejecutar el envío mediante un puerto fuera de la transacción SQL de reclamación. **H4**.
9. Registrar intentos, último error, próxima ejecución, pendientes y antigüedad. Proporcionar inspección de solo lectura. Cargar políticas de laboratorio mediante un script explícito y reproducible, con selección inequívoca de la vigente por partner. **H2, H6**.
10. Conectar las factorías SQL con `config/bootstrap.py` y demostrar el flujo mediante handlers reales y tres UoW SQL. Documentar arranque de PostgreSQL, migraciones, carga de políticas y suite completa habilitada. Registrar evidencia Red → Green → Refactor y de reinicio. **H6**.



## Transacciones e inbox — H1


| Ejecución           | Confirmación atómica                                                                                       |
| ------------------- | ---------------------------------------------------------------------------------------------------------- |
| Registrar solicitud | Solicitud versión 1 + evento de registro en outbox.                                                        |
| Evaluar registro    | Inbox `reglas_partner.evaluar` + evaluación inicial + registro de origen + evento de evaluación en outbox. |
| Aplicar resultado   | Inbox `solicitudes.aplicar` + solicitud versión 2 + evento de solicitud lista o rechazada en outbox.       |


El handler consumidor prepara su entrada dentro de la UoW que ya abre. El mecanismo devuelve si la entrada es nueva o ya está confirmada. Una entrada nueva solo queda procesada cuando el handler confirma toda la ejecución. No añadir un consumidor que confirme inbox por fuera ni una UoW que abarque las tres etapas. Los nombres de consumidor son estables y se reutilizan en 05; no incluyen ID de proceso o réplica.

Una entrada ya confirmada no repite efectos. Si el negocio determina que no hay cambios pero la entrada es nueva y válida, se confirma únicamente esa entrada; revisar los retornos tempranos existentes. Un conflicto o error revierte la entrada preparada. La restricción SQL resuelve las entradas concurrentes; no basta una consulta previa.

Si falta una política válida, se conserva la solicitud recibida, sin evaluación, inbox procesado ni salida de resultado. Tras corregir la política, la reentrega puede continuar. Un siniestro con aprobación falsa y política válida produce rechazo empresarial y confirma evaluación/salida; no es un error técnico. La política inválida mantiene su precedencia sobre ese rechazo.

Retirar eventos pendientes del agregado no los entrega al bus. `registrar_salida` prepara su almacenamiento; solo el commit los vuelve visibles al lector del outbox. Reglas registra `evaluacion.evento`, conservando su identidad. Un fallo posterior no deshace los pasos previamente confirmados. El ACK del transporte solo podrá darse tras éxito confirmado; su implementación real pertenece a 05.

## Reconstrucción e idempotencia — H2 y H3

Conservar el registro de origen completo en almacenamiento propietario de Reglas para implementar `guardar_origen` y `obtener_origen`. Su comparación no depende de tablas de Solicitudes ni de filas de outbox que puedan eliminarse después. Persistir evaluación y origen juntos. Tras una evaluación inicial, una reentrega equivalente reutiliza el resultado original aunque cambie o desaparezca la política vigente; un origen incompatible mantiene el conflicto.

Los mapeadores preservan UUID, instantes con zona y precisión, versiones, enumeraciones y `None` frente a `False` en aprobación. El resultado de Solicitudes conserva ID e instante del evento recibido, evaluación, solicitud, partner, política y versiones, además de admisibilidad y red o motivo. Cargar mediante `reconstruir`, nunca `registrar` ni el servicio evaluador. Una consulta de persistencia no crea eventos pendientes ni importa tipos de Reglas en el dominio de Solicitudes.

Las políticas de ejemplo tienen identidad y versión explícitas. El repositorio obtiene una única política vigente por partner; documentar su selección y permitir cambiarla mediante la carga de laboratorio sin modificar evaluaciones históricas. No introducir una API administrativa.

La unicidad SQL complementa la igualdad exacta de `DatosSolicitud` del plan 03; no sustituye sus comprobaciones. La misma referencia en partners diferentes sigue siendo válida. Los reintentos equivalentes devuelven la misma confirmación incluso tras un estado terminal.

El repositorio de Solicitudes conserva la versión cargada antes de que el agregado cambie. La actualización exige esa versión y guarda la nueva, manteniendo 1 → 2; no incrementarla de nuevo automáticamente. Verificar una fila afectada. El fallo por versión o unicidad revierte el intento completo antes de abrir una nueva lectura. Solo las colisiones identificadas se resuelven como repetición/conflicto; otros errores se propagan. Acotar los reintentos y no confirmar salidas del intento perdedor. Las excepciones de SQLAlchemy no deben convertirse en dependencias de dominio o aplicación.

## Serialización durable y entrega — H5

Definir un formato de almacenamiento versionado por tipo para `SolicitudPartnerRegistrada`, `ReglasDePartnerEvaluadas`, `SolicitudPartnerListaParaAtencion` y `SolicitudPartnerRechazada`. Incluir tipo, versión del formato, `id_evento`, `instante`, identidad de solicitud, versión de solicitud y payload completo. Un formato desconocido o payload inválido falla de manera visible; no se descarta silenciosamente. La serialización inválida revierte también el efecto de negocio.

Los codecs concretos viven en infraestructura del módulo propietario. El mecanismo outbox común recibe la representación serializada y metadatos; no conoce políticas ni estados empresariales. Los campos de dominio `id_evento` e `instante` se conservan y se corresponderán con `event_id` y `occurred_at` del sobre de transporte, sin renombrar el dominio ni generar valores al reintentar. Los metadatos adicionales y el contrato público definitivo se cierran en 05.

Separar identidad del evento e identidad de su entrega. Cada fila pendiente representa una publicación a un destino lógico, con unicidad por evento/destino y marca propia. Una sola publicación puede alimentar varias suscripciones del broker; eso no necesita una fila por consumidor. Si 05 define publicaciones a destinos distintos, cada una tendrá seguimiento independiente. 04 prueba este mecanismo con destinos de laboratorio, sin fijar tópicos ni contratos públicos del equipo.

Los reintentos leen la representación persistida; no reconstruyen el hecho consultando el estado mutable del agregado. La conversión posterior al contrato público debe conservar identidad estable por publicación y el contenido del hecho original.

## Reservas temporales del outbox — H4

Un lease es una reserva temporal para que un worker envíe una entrega pendiente. Reclamar un lote en una transacción corta asigna token nuevo, propietario y vencimiento; solo se reclaman pendientes disponibles o reservas vencidas. La duración es configurable. Usar un criterio temporal consistente para comprobar vencimiento.

Después de confirmar la reserva, publicar fuera de esa transacción. Marcar enviado únicamente tras acuse positivo; ante fallo, registrar el intento y programar la próxima ejecución. Finalizar o reprogramar exige que token, propietario y vigencia sigan correspondiendo a la reserva actual. Si no coinciden, no modificar la fila.

Ejemplo obligatorio: A reserva y se detiene; vence su reserva; B toma la entrega con otro token; A vuelve tarde. A no puede marcarla enviada ni reprogramarla, porque ya no tiene la reserva vigente. B puede continuar. Una caída entre envío y marca permite un envío repetido con la misma identidad: inbox e idempotencia evitan repetir el efecto; no se promete exactly-once.

En 04 se prueban reclamación y confirmación con PostgreSQL y acuses/fallos simulados. El arranque del despacho continuo desde `config/bootstrap.py`, el acuse real y la caída frente a Pulsar se completan en 05.

## Organización de archivos — H6

Rutas desde la raíz del repositorio; conservar la [convención común](README.md#convención-de-nombres-para-todos-los-planes). Crear únicamente archivos con contenido y responsabilidad reales.


| Ubicación                                                             | Archivos                                                                                                                                              | Responsabilidad                                                                                                               |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `src/solicitudes_partner/modulos/solicitudes/infraestructura/`        | `orm.py`, `mapeadores.py`, `repositorios.py`, `unidad_trabajo.py`, `serializacion.py`                                                                 | Modelo SQL propio, reconstrucción, persistencia con versión, UoW de Solicitudes y codecs de sus tres eventos.                 |
| `src/solicitudes_partner/modulos/reglas_partner/infraestructura/`     | `orm.py`, `mapeadores.py`, `repositorios.py`, `unidad_trabajo.py`, `serializacion.py`                                                                 | Políticas, evaluaciones y origen; repositorios, UoW de Reglas y codec de evaluación.                                          |
| `src/solicitudes_partner/seedwork/aplicacion/`                        | `unidad_trabajo.py` existente                                                                                                                         | Extender el puerto con preparación de entrada procesada; conservar salidas y ciclo transaccional.                             |
| Misma ubicación                                                       | `publicacion.py`                                                                                                                                      | Puerto de envío con resultado explícito de confirmación; sin SDK.                                                             |
| `src/solicitudes_partner/seedwork/infraestructura/`                   | `unidad_trabajo_sqlalchemy.py`, `inbox.py`, `outbox.py`, `despacho_outbox.py`                                                                         | Ciclo SQL común, almacenamiento de entradas/salidas y despacho de un lote con reserva. Sin rutas de negocio.                  |
| `src/solicitudes_partner/modulos/solicitudes/aplicacion/handlers/`    | `registrar_solicitud.py`, `aplicar_resultado.py` existentes                                                                                           | Recuperación idempotente del registro y confirmación de inbox junto con transición; conservar traducción al resultado propio. |
| `src/solicitudes_partner/modulos/reglas_partner/aplicacion/handlers/` | `evaluar_registro.py` existente                                                                                                                       | Confirmar entrada, origen, evaluación y salida; tratar retornos y colisiones.                                                 |
| `src/solicitudes_partner/config/`                                     | `database.py`, `bootstrap.py` existentes                                                                                                              | Reutilizar recursos y conectar factorías SQL y codecs con dependencias explícitas.                                            |
| Raíz y `migraciones/`                                                 | `alembic.ini`, `env.py`, `versions/`                                                                                                                  | Revisiones de esquema, restricciones e índices; migración explícita.                                                          |
| Raíz                                                                  | `docker_compose.yaml`, `.env.example`, `pyproject.toml`, `uv.lock`                                                                                    | PostgreSQL local, configuración de ejemplo y dependencias actualizadas.                                                       |
| `scripts/`                                                            | `cargar_politicas.py`                                                                                                                                 | Configuración reproducible de políticas de laboratorio.                                                                       |
| `tests/unitarias/aplicacion/dobles/`                                  | Archivos existentes                                                                                                                                   | Mantener dobles compatibles con los puertos extendidos e inbox, sin conexión SQL.                                             |
| `tests/integracion/`                                                  | `conftest.py`, `test_migraciones.py`, `test_repositorios.py`, `test_unidad_trabajo.py`, `test_concurrencia.py`, `test_outbox.py`, `test_flujo_sql.py` | PostgreSQL real, barreras de concurrencia, fallos por etapa y recuperación.                                                   |
| `tests/unitarias/`                                                    | `test_serializacion.py`                                                                                                                               | Ida/vuelta e incompatibilidad de formatos sin infraestructura externa.                                                        |
| `docs/plans/`                                                         | `evidencia-04-sqlalchemy-uow-outbox.md`                                                                                                               | Crear al ejecutar: evidencia real, comandos, resultados y límites.                                                            |


No compartir entidades ORM entre módulos. El repositorio puede traducir errores SQL a excepciones propias de aplicación para coordinar recuperación; añadirlas en los archivos de excepciones existentes según necesidad. No crear otro bootstrap ni una fachada `contratos.py`. Actualizar las comprobaciones de distribución e aislamiento para las nuevas rutas. API, dominio e imports no arrancan consumidores ni migraciones.

## Pruebas

Usar Red → Green → Refactor para el comportamiento nuevo. Unitarias con dobles; integración con PostgreSQL real. SQLite no sustituye los ensayos de atomicidad, restricciones, bloqueo o concurrencia. Las pruebas concurrentes usan conexiones distintas y barreras para forzar la carrera, no solo invocaciones consecutivas.


| Criterio                       | Evidencia exigida                                                                                                                                                                                                                                    |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **H1 — Atomicidad**            | Fallar tras preparar inbox, tras cambiar negocio, al preparar outbox y en commit. Otra sesión observa todo o nada. Cada UoW tiene sesión propia y cierra recursos. Reglas fallida conserva recepción; transición fallida conserva evaluación.        |
| **H1 — Reentrega**             | Reintentar después de fallo completa el paso. Repetición confirmada no duplica efecto; entrada nueva válida sin cambios se confirma. Dos consumidores distintos no se deduplican entre sí.                                                           |
| **H2 — Reconstrucción**        | Ida/vuelta de recibida, lista con cada red y rechazada; UUID, fechas, versiones y aprobación preservados; lectura no genera pendientes. Solicitudes conserva tipos locales.                                                                          |
| **H2 — Origen y política**     | Reiniciar recursos y reentregar tras cambiar o retirar política: evaluación original sin nueva salida. Origen incompatible sigue en conflicto. Política ausente no deja inbox procesado y permite reintento tras corregirla.                         |
| **H3 — Registro**              | Dos registros equivalentes compiten: una solicitud, una salida y misma confirmación. Contenido diferente produce conflicto sin sobrescritura. Referencia igual entre partners distintos es válida. Reintento tras estado terminal permanece estable. |
| **H3 — Evaluación/transición** | Dos evaluaciones del mismo origen producen una evaluación inicial; dos aplicaciones del mismo resultado producen un evento terminal. Cada invocación tiene resultado comprobado.                                                                     |
| **H3 — Versión**               | Cargar versión 1 en dos sesiones y forzar escritura obsoleta directamente por repositorio, fuera del filtro inbox: falla sin outbox del perdedor. Recuperación tras rollback conserva al ganador.                                                    |
| **H4 — Reservas**              | Reclamadores concurrentes no poseen la misma reserva vigente; vencimiento permite recuperar; A atrasado no finaliza ni reprograma la reserva de B; fallo de envío queda reintentable.                                                                |
| **H5 — Formatos**              | Los cuatro eventos se guardan y decodifican desde sesión nueva conservando igualdad; payload inválido revierte negocio; versión desconocida falla visiblemente.                                                                                      |
| **H5 — Entregas**              | Reintento conserva ID y contenido; destinos independientes conservan marcas independientes. Fallo después de envío simulado y antes de marca permite recuperar el pendiente.                                                                         |
| **H6 — Recorrido**             | Migrar base vacía, cargar políticas y recorrer handlers mediante tres UoW SQL, observando estados intermedios. Reiniciar recursos y continuar desde salidas persistidas sin dobles de negocio.                                                       |


El recorrido integrado cubre red general, red homologada, rechazo por aprobación falsa, instalación sin aprobación y política ausente. Logs solos no acreditan efectos; consultar filas confirmadas desde sesiones nuevas y contar eventos/entradas pertinentes.

## Cierre

El cierre exige todos los criterios H1–H6 y evidencia real en el archivo indicado. Documentar en README comandos reproducibles de arranque, disponibilidad de PostgreSQL, migraciones, políticas, pruebas unitarias/API/integración, lint, formato, tipado y verificación de distribución. Integración forma parte obligatoria de la suite habilitada en 04 y falla claramente si falta infraestructura; no ocultarla mediante skips.

No existe CI en el árbol auditado. Si se incorpora en este incremento, describirla como configuración nueva e incluir PostgreSQL, migraciones e integración obligatoria; no afirmar ejecución remota sin comprobarla. La validación local completa es exigible aunque no se cree workflow.

Conservar documentada la frontera: persistencia y recuperación local probadas en 04; Pulsar automático en 05; HTTP y CQRS completo en 06. Mantener el estado pendiente hasta implementar y verificar. No hacer commit ni push por ejecutar este plan.

## Resultado de ejecución

Se implementaron y verificaron H1–H6: 203 pruebas aprobadas, incluidas 36 con PostgreSQL real, más lint, formato, tipado y distribución. El transporte de laboratorio permite comprobar el despacho de lotes y sus fallos; Pulsar automático permanece en 05.

La organización se concretó con archivos auxiliares adicionales de responsabilidad acotada: `config/persistencia.py` para las factorías SQL, `config/serializacion.py` para seleccionar codecs, `seedwork/infraestructura/orm.py` para metadata y tipos SQL comunes, `seedwork/infraestructura/serializacion.py` para lectura tipada de primitivas y `seedwork/aplicacion/excepciones.py`/`reintentos.py` para colisiones recuperables. `scripts/inspeccionar_outbox.py` proporciona inspección sin modificar datos. El bootstrap conserva su ubicación y carga la composición SQL al invocarla. No se crearon workflows ni se hizo commit/push.
