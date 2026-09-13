# Entrada de Solicitudes de Partner

Microservicio de Entrada de Solicitudes de Partner de Hogar de los Alpes, para el canal B2B2C. Su construcción parte de dos módulos internos: Solicitudes de Partner y Reglas de Partner, con arquitectura hexagonal y seedwork local.

## Estado actual

Los **planes 01–06 están implementados y verificados localmente**. El flujo Solicitudes → Reglas → Solicitudes avanza automáticamente mediante bus interno, con tres UoW, inbox y outbox en PostgreSQL. Un despachador publica `SolicitudDePartnerListaParaAtencion.v1` por Pulsar. La API permite registrar y consultar; un proyector conserva recibidas, listas y rechazadas. Los cuatro bucles se ejecutan dentro del proceso FastAPI y su lifespan administra el arranque y la parada. [Evidencia de 06](docs/plans/evidencia-06-cqrs-api.md).

| Componente | Estado |
|---|---|
| Paquete Python y entorno uv | Instalación reproducible con `uv.lock`. |
| FastAPI | Registro `POST /solicitudes`, GET por ID, listado paginado y `GET /health/live`. |
| SQLAlchemy y psycopg | Factoría de Engine y sesiones independientes, sin conexión durante el arranque. |
| Módulos y seedwork | Solicitud, política, evaluación, agregación raíz, eventos y puertos implementados. |
| Verificación local | 258 pruebas aprobadas, incluidas 55 de integración; lint, formato, tipado y distribución correctos. Recorrido HTTP con un proceso FastAPI y recuperación CQRS; verificación del cambio en lifespan documentada en la evidencia de 06. |
| Contratos internos | Registro, evaluación, solicitud lista y rechazada, con versiones y datos inmutables. |
| Handlers y bus local | Registro idempotente, evaluación inicial única, transición y despacho por consumidor comprobados con UoW en memoria y SQL; el despacho durable ejecuta el handler antes de confirmar la entrega. |
| Persistencia | PostgreSQL, Alembic, ORM/mapeadores, inbox y outbox con reservas recuperables. |
| Pulsar | Publicación pública Avro v1 y tópico CQRS independiente, con proyección transaccional e idempotente de los tres estados. |

Los resultados corresponden a la corrida registrada del 12 de septiembre de 2026. [Evidencia del plan 01](docs/plans/evidencia-01-base-tecnologica.md) · [Evidencia del plan 02](docs/plans/evidencia-02-modelo-dominio-seedwork.md) · [Evidencia del plan 03](docs/plans/evidencia-03-comandos-eventos-internos.md) · [Evidencia del plan 04](docs/plans/evidencia-04-sqlalchemy-uow-outbox.md) · [Evidencia del plan 05](docs/plans/evidencia-05-pulsar-contratos.md) · [Modelo de dominio](docs/modelo-dominio.md) · [Planes de construcción](docs/plans/README.md).

## Entorno

Python 3.12.3 y uv 0.10.9. Plataforma comprobada: Ubuntu 24.04, Linux x86_64. Instalar uv según su [documentación oficial](https://docs.astral.sh/uv/getting-started/installation/). Desde la raíz de este servicio:

```bash
uv sync --locked
```

El comando instala Python si es necesario, crea `.venv` e instala las versiones de `uv.lock`. No requiere PostgreSQL, Pulsar ni Docker. El backend de construcción `uv_build` también tiene versión exacta en `pyproject.toml`.

## Ejecutar

```bash
uv run --locked uvicorn solicitudes_partner.api.app:create_app --factory
```

En otra terminal:

```bash
curl --fail http://127.0.0.1:8000/health/live
```

Respuesta predeterminada: HTTP 200 y `{"status":"ok","service":"solicitudes-partner"}`. Detener el servidor con Ctrl+C. Liveness comprueba que el proceso responde; no comprueba disponibilidad de infraestructura. OpenAPI está disponible en `/docs`.

## Configuración

| Variable | Predeterminado | Efecto |
|---|---|---|
| `PARTNER_SERVICE_NAME` | `solicitudes-partner` | Nombre que devuelve liveness. |
| `PARTNER_DATABASE_URL` | Ausente o vacía | Sin Engine. Si existe, debe usar `postgresql+psycopg://`. |
| `PARTNER_PULSAR_URL` | `pulsar://127.0.0.1:6650` | Broker para publicación externa. |
| `PARTNER_PULSAR_TOPIC` | `persistent://public/default/solicitud-partner-lista-v1` | Tópico del contrato público v1. |
| `PARTNER_CQRS_TOPIC` | `persistent://public/default/solicitud-partner-lectura-v1` | Tópico independiente para los tres estados. |
| `PARTNER_CQRS_SUBSCRIPTION` | `solicitudes-lectura-v1` | Suscripción durable del proyector. |

`.env.example` enumera las variables, pero no se carga automáticamente. Exportarlas en la terminal o configurarlas en el entorno de ejecución. No guardar credenciales reales en archivos versionados.

`create_app` acepta `Settings` y una factoría de base para pruebas. Lee el entorno al crear cada aplicación, sin configuración global cacheada. Si hay URL, el lifespan construye Engine/sessionmaker, verifica los destinos pendientes e inicia los bucles de procesamiento; al cerrar espera su parada y libera el Engine, también ante excepciones. Las migraciones deben aplicarse antes del arranque. Cada invocación de `session_factory()` entrega una sesión independiente. Su propietario debe cerrarla; las UoW SQL controlan las transacciones. La API conecta registro y consultas mediante dependencias separadas; no ejecuta migraciones. Sin URL de base, solo ofrece liveness y no inicia procesamiento.

## Persistencia local

El entorno de 04 usa PostgreSQL 17.6, SQLAlchemy 2.0.52, psycopg 3.3.5 y Alembic 1.20.0. Compose publica exclusivamente en `127.0.0.1:55434`, con volumen propio y credenciales de laboratorio. Las dependencias Python están fijadas en `uv.lock`.

```bash
docker compose -f docker-compose.yaml up -d --wait
export PARTNER_DATABASE_URL='postgresql+psycopg://partner:partner_local@127.0.0.1:55434/partner'
uv run --locked alembic upgrade head
uv run --locked python scripts/cargar_politicas.py
uv run --locked python scripts/inspeccionar_outbox.py
```

La carga predeterminada establece red general para partner `00000000-0000-0000-0000-000000000002`, política `00000000-0000-0000-0000-000000000003`, versión 1. Es una configuración ficticia, repetible. Para sustituir su política vigente por la versión 2 con red homologada:

```bash
uv run --locked python scripts/cargar_politicas.py --version 2 --red HOMOLOGADA_PARTNER
```

`--id-partner` y `--id-politica` permiten cargar otros ejemplos. Hay una fila de política vigente por partner; las evaluaciones conservan su resultado e identidad/versión originales, incluso después de sustituir esa fila. La carga es administrativa y explícita, sin endpoint nuevo.

Los esquemas `solicitudes` y `reglas_partner` contienen tablas de sus módulos; `mensajeria` contiene inbox, outbox y `eventos`, un archivo de documentos completos confirmado en la misma transacción. El archivo conserva los documentos de los eventos; no representa entregas pendientes ni Event Sourcing. `lectura.solicitudes` contiene la vista CQRS, con versión, datos desnormalizados y fecha de proyección. Los datos compuestos y eventos se conservan en JSONB mediante mapeadores y formatos explícitos; identidad, referencia, estado y versión de solicitudes tienen columnas relacionales. El origen de evaluación se conserva separado del outbox. El modelo de dominio no es ORM.

`config/bootstrap.py` compone los handlers y despachadores. `config/procesamiento.py` conecta el lifespan con los ciclos de `seedwork/infraestructura/ciclos.py`. `config/rutas.py` centraliza las rutas `reglas_partner.evaluar`, `solicitudes.aplicar`, `integracion.solicitud_lista.v1` y `cqrs.solicitud.v1`. El rechazo alimenta CQRS, pero no el contrato público de solicitud lista. No se crean consumidores Pulsar para comunicación entre los dos módulos.

Cada entrega tiene identidad estable por evento/destino. `DespachadorOutbox` reserva, llama al puerto `Publicador` fuera de la transacción y marca solo el éxito. La entrega interna espera el commit del handler; `send()` externo espera al broker. Ambos ciclos son independientes, secuenciales, de una entrega por lote, con pausa de 0,2 s, reserva de 30 s y reintento tras 5 s. El cliente limita conexión, operación y envío a 5 s por operación. Si cae el proceso, el siguiente recupera reservas vencidas y el inbox evita repetir efectos. Los timeouts no equivalen a ausencia de publicación.

`inspeccionar_outbox.py` muestra pendientes, antigüedad, intentos y último error. Un documento inválido conserva su salida para intervención; puede detenerse el despachador mientras se corrige la causa. Los destinos antiguos desconocidos bloquean el arranque para exigir inspección; no se descartan automáticamente.

Para observar el recorrido con PostgreSQL y bus de laboratorio:

```bash
uv run --locked pytest tests/integracion/test_flujo_sql.py -v
```

Para detener el entorno preservando el volumen:

```bash
docker compose -f docker-compose.yaml stop
```

## Verificar

```bash
uv sync --locked
docker compose -f docker-compose.yaml up -d --wait
uv run --locked pytest tests -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests scripts migraciones
uv run --locked python scripts/verify_distribution.py
```

El script de distribución crea un entorno temporal con dependencias de producción del lockfile, construye sdist y wheel, reinstala ese wheel sin resolver otras dependencias y lo importa desde fuera del árbol fuente con Python en modo aislado. Elimina sus archivos temporales al terminar. Para generar artefactos conservables en `dist/`, ejecutar `uv build`.

La suite completa incluye pruebas unitarias, API, contratos Avro e integración. PostgreSQL usa bases temporales `partner_test_<uuid>` que se eliminan al finalizar; requiere permiso de crear bases. Pulsar usa tópicos únicos y consumidores con SQLite temporal. La prueba de caída detiene y reinicia **el servicio Pulsar de este Compose**; ejecutar en laboratorio local sin otros experimentos concurrentes. Si falta infraestructura, las pruebas fallan sin skips. `PARTNER_TEST_DATABASE_URL`, `PARTNER_TEST_PULSAR_URL` y `PARTNER_TEST_PULSAR_ADMIN_URL` permiten configurar conexiones; la prueba que controla Compose exige el broker local predeterminado.

TestClient usa `httpx2`, requerido por la versión resuelta de Starlette; por ello sustituye al `httpx` inicialmente propuesto. Hay una advertencia visible de Starlette por el alias obsoleto `anyio.abc.BlockingPortal`. No se modifica código de terceros ni se suprime esa advertencia. Las deprecaciones originadas en el paquete propio hacen fallar pytest.

## Ejecutar el flujo y consumir el evento

Preparar el tópico, retención y suscripciones siguiendo el [contrato público](docs/contratos/README.md). El cliente `pulsar-client[avro]` 3.13.0 forma parte del lockfile; el broker local es Pulsar 4.1.3, con volumen persistente y administración en `127.0.0.1:18086`.

Con `PARTNER_DATABASE_URL` exportada, iniciar el servicio:

```bash
uv run --locked uvicorn solicitudes_partner.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

El `lifespan` de FastAPI inicia el despacho interno, la publicación pública, la publicación CQRS y el consumidor de proyección en cuatro hilos del mismo proceso. Las llamadas bloqueantes de SQLAlchemy y `pulsar-client` quedan fuera del event loop HTTP. Importar módulos o construir la aplicación no inicia ciclos. Al cerrar FastAPI se solicita la parada de todos los bucles, se espera a que terminen y cierren los clientes Pulsar, y después se cierra la base.

Tras aplicar migraciones y cargar la política de laboratorio, en otra terminal:

```bash
uv run --locked python scripts/registrar_solicitud.py --referencia DEMO-05
uv run --locked python scripts/consumir_eventos.py --suscripcion atencion --base /tmp/partner-atencion.db
uv run --locked python scripts/consumir_eventos.py --suscripcion estadisticas --base /tmp/partner-estadisticas.db
uv run --locked python scripts/inspeccionar_outbox.py
```

El registro solo confirma recepción. El despacho interno evalúa y cambia el estado; el externo publica. Cada consumidor persiste una fila en su propia tabla SQLite `recibidos`. Repetir la misma referencia y datos no crea otra solicitud; usar otra referencia para otro ensayo. `--aprobacion no` permite registrar un siniestro que terminará rechazado, sin publicación externa. Para instalación sin aprobación: `--tipo INSTALACION --aprobacion ausente`.

Para probar una caída del consumidor después de persistir, agregar `--interrumpir-tras-commit`: termina con código 75 antes del ACK; al reiniciarlo con la misma suscripción/base reconoce el duplicado. La suite automatiza este caso y la caída tras publicación antes de marcar el outbox.

## Organización

```text
src/solicitudes_partner/
  api/
    app.py
  config/
    procesamiento.py
    settings.py
    database.py
  modulos/
    solicitudes/
      aplicacion/
      dominio/
      infraestructura/
    reglas_partner/
      aplicacion/
      dominio/
      infraestructura/
  seedwork/
    aplicacion/
    dominio/
    infraestructura/
tests/
  unitarias/
  api/
  integracion/
  contratos/
scripts/
  verify_distribution.py
docs/plans/
```

Las carpetas y los nuevos identificadores propios de clases, funciones, variables, estados y eventos se nombran en español, sin tildes y con el vocabulario del Event Storming. La base tecnológica ya implementada conserva por ahora sus nombres; los identificadores impuestos por bibliotecas y herramientas mantienen su forma original. Se conservan los nombres técnicos `api`, `config`, `seedwork`, `src` y `tests`.

`api/` contiene el adaptador HTTP y la creación de la aplicación web. `config/` contiene la lectura del entorno, la construcción de recursos SQLAlchemy y el bootstrap del flujo interno. Los módulos separan entidades y objetos valor; Reglas también separa servicios y excepciones. Los eventos se definen y se importan directamente desde `dominio/eventos.py` de su módulo. El handler receptor de Solicitudes traduce el evento de Reglas a `ResultadoEvaluacion` y enumeraciones propias; su dominio no depende de Reglas. No hay fachadas `contratos.py`. Aplicación separa comandos, confirmaciones, excepciones, UoW y handlers; `config/bootstrap.py` conecta los tres handlers con dependencias explícitas. El bus local vive en `seedwork/infraestructura/bus_eventos_local.py`; los repositorios y UoW falsos están exclusivamente en `tests/unitarias/aplicacion/dobles/`. Seedwork separa entidades, objetos valor y eventos en archivos propios. Véase el [modelo implementado](docs/modelo-dominio.md) para responsabilidades, invariantes y límites.

### Presentación y seedwork

Por ahora, la presentación HTTP vive en `api/`. No existe `seedwork/presentacion/`: se podrá incorporar cuando haya mecanismos comunes concretos, como un formato de errores y sus manejadores HTTP reutilizados por ambos módulos. Los endpoints y DTO específicos conservarán su ubicación en el adaptador correspondiente. Dominio y aplicación no deberán depender de ese soporte de presentación.

Seedwork es local a este servicio y contiene las abstracciones utilizadas por los modelos y los puertos previstos para los próximos incrementos. No es una biblioteca de negocio compartida entre los cuatro microservicios.

## Próximos incrementos

El siguiente paso es el [plan 07: integración y experimentación](docs/plans/07-integracion-experimentos.md). Siguen pendientes los experimentos de carga, la integración grupal y el despliegue compartido.

Entrada y una porción de Reglas cuentan como **un servicio** de la POC. Los consumidores SQLite son herramientas de laboratorio; Orquestación, Cotizaciones y Scoring empresariales quedan fuera de este repositorio. Standalone no acredita un clúster.

`RelojActual` e `IdentificadoresAleatorios` son adaptadores únicos en `seedwork/infraestructura/reloj.py` e `identificadores.py`; implementan los puertos de aplicación y se reutilizan en el servicio, scripts y pruebas SQL.

La UoW delega el archivo de eventos y la creación de salidas a `RepositorioSalidasSQL`, que utiliza su misma sesión sin confirmar transacciones propias. El repositorio de despacho conserva sus transacciones cortas para reservas y acuses. `mapeadores.py` de Solicitudes contiene los mapeos SQL; `mapeadores_eventos.py` transforma los mensajes Avro de integración y de lectura. `repositorios.py` agrupa la persistencia de solicitudes, las consultas y las actualizaciones de la vista; `proyecciones.py` coordina su transacción con el registro del evento procesado. Importar persistencia SQL no carga Pulsar.


## API y CQRS — laboratorio del plan 06

Preparar una base nueva para esta demostración, sin borrar datos anteriores. Este comando de creación se ejecuta una sola vez; en un reinicio se reutiliza la base existente:

```bash
docker compose up -d --wait postgres
docker compose up -d --wait pulsar
docker compose exec postgres createdb -U partner partner_cqrs_demo
export PARTNER_DATABASE_URL='postgresql+psycopg://partner:partner_local@127.0.0.1:55434/partner_cqrs_demo'
export PARTNER_CQRS_TOPIC='persistent://public/default/solicitud-partner-lectura-demo-v1'
export PARTNER_CQRS_SUBSCRIPTION='solicitudes-lectura-demo-v1'
uv run --locked alembic upgrade head
uv run --locked python scripts/cargar_politicas.py
```

En esa misma terminal iniciar el único proceso del servicio:

```bash
uv run --locked uvicorn solicitudes_partner.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

La suscripción CQRS se abre automáticamente antes de publicar los primeros mensajes de lectura. Si Pulsar no está disponible, se reintenta en segundo plano y el flujo interno puede seguir registrando y evaluando; las salidas permanecen en outbox. En los reinicios se reutilizan la base, el tópico y la suscripción. La publicación pública también arranca con la API; sus consumidores externos preparan sus suscripciones según el contrato.

Registrar una solicitud:

```bash
curl -i http://127.0.0.1:8000/solicitudes \
  -H 'Content-Type: application/json' \
  -H 'X-Partner-Laboratorio: 00000000-0000-0000-0000-000000000002' \
  -d '{"referencia_externa":"SIN-DEMO-1","categoria":"plomeria","tipo":"SINIESTRO","aprobacion_previa":true}'
```

Devuelve `202`, `id_solicitud`, `recepcion_confirmada: true` y `Location`. Consultar esa URL con el mismo encabezado de partner. Para listar:

```bash
curl -s 'http://127.0.0.1:8000/solicitudes?limite=20&desplazamiento=0' \
  -H 'X-Partner-Laboratorio: 00000000-0000-0000-0000-000000000002'
```

`X-Partner-Laboratorio` selecciona un UUID no nulo para el ejercicio; cualquiera que acceda a la API local puede seleccionarlo. No autentica al cliente ni representa autorización de producción. El body no admite `id_partner`; registro y consultas usan la dependencia de identidad, sustituible en pruebas. Las consultas filtran por partner dentro de su repositorio.

| Operación | Respuesta |
|---|---|
| Registro nuevo o repetición idéntica | `202`, mismo ID para la misma referencia y datos. |
| Misma referencia del partner con otro contenido | `409`. |
| Siniestro sin aprobación declarada, tipo inválido o datos vacíos | `422`. `false` sí se recibe y produce rechazo empresarial posterior. |
| Consulta de fila visible | `200`; recibida, lista o rechazada según lo proyectado. |
| Fila ausente o perteneciente a otro partner | `404`, «no disponible en la vista». No afirma inexistencia en escritura. |
| Persistencia sin configurar o temporalmente no disponible | `503`, sin confirmación de recepción. |

La consulta usa únicamente `lectura.solicitudes`. Puede retrasarse y devolver `404` inmediatamente después del POST; el cliente que obtuvo confirmación puede reintentar. El listado ordena por creación e ID, con límite 1–100 y desplazamiento no negativo; no ofrece un snapshot entre páginas bajo inserciones concurrentes.

Para observar `RECIBIDA`, usar un partner sin política. Registrar conserva la solicitud mientras la evaluación espera configuración. Cargar su política con `scripts/cargar_politicas.py --id-partner UUID` permite continuar automáticamente. Para rechazo usar una referencia nueva con `aprobacion_previa:false`; la vista conserva el motivo y no inventa una red.

Para ensayar recuperación, registrar sin política, observar `RECIBIDA`, detener FastAPI con Ctrl+C, cargar la política y reiniciar el mismo servicio. La evaluación continúa y la vista converge sin recrear la base ni cambiar de suscripción. `seedwork/infraestructura/ciclos.py` comparte repetición/parada; bootstrap compone, infraestructura procesa y los repositorios ejecutan SQL. Los logs `Proyeccion confirmada` incluyen ID, versión y latencia desde el evento hasta después del commit.

La POC comparte servidor y credencial PostgreSQL. Cada operación abre su propia sesión; no exige roles separados, migración histórica, autenticación de producción ni despliegue independiente de consultas. [Contrato CQRS y HTTP](docs/contratos/lectura.md).

### Construcción de dependencias

Las funciones `componer_*` de `config/bootstrap.py` actúan como fábricas explícitas de handlers, despachadores y del consumidor de proyección. Las funciones `crear_uow_*` de `config/persistencia.py` construyen las unidades de trabajo. No se requiere una fábrica genérica para seleccionar repositorios: cada operación declara su dependencia y recibe la sesión o la fábrica de sesiones correspondiente.

### Despliegue conjunto de la POC

API, consumidores y relay comparten un servicio y un proceso Uvicorn por instancia. Se conservan componentes y transacciones separados; escalan y se reinician juntos. No se usa `--reload` para desplegar ni se crean procesos Uvicorn adicionales.

Para Cloud Run, configurar facturación por instancia (CPU disponible fuera de peticiones), mínimo una instancia y máximo una para la demostración. Uvicorn recibe SIGTERM y ejecuta el cierre del lifespan. Cloud Run puede terminar una instancia incluso con un mínimo configurado; outbox, inbox y la suscripción durable permiten recuperar lo pendiente si la operación no alcanza a finalizar. Esta configuración queda prevista en el plan 08; no se desplegó en la nube.

Referencias: [lifespan del BFF del tutorial 9](https://github.com/MISW4406/tutorial-9-bff/blob/main/src/bff_web/main.py), [consumidor con aiopulsar](https://github.com/MISW4406/tutorial-9-bff/blob/main/src/bff_web/consumidores.py), [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/) y [CPU y facturación de Cloud Run](https://docs.cloud.google.com/run/docs/configuring/billing-settings). Aquí se conserva `pulsar-client` síncrono con hilos administrados desde lifespan.
