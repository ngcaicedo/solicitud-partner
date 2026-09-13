# Entrada de Solicitudes de Partner

Microservicio de Entrada de Solicitudes de Partner de Hogar de los Alpes, para el canal B2B2C. Su construcción parte de dos módulos internos: Solicitudes de Partner y Reglas de Partner, con arquitectura hexagonal y seedwork local.

## Estado actual

Los **planes 01–04 están implementados y verificados localmente**. El registro, la evaluación y la transición cuentan con repositorios SQL, tres UoW independientes, inbox y outbox en PostgreSQL. Las pruebas avanzan las entregas explícitamente mediante transporte de laboratorio; Pulsar automático y la API de negocio pertenecen a 05–06.

| Componente | Estado |
|---|---|
| Paquete Python y entorno uv | Instalación reproducible con `uv.lock`. |
| FastAPI | Factoría de aplicación y `GET /health/live`. |
| SQLAlchemy y psycopg | Factoría de Engine y sesiones independientes, sin conexión durante el arranque. |
| Módulos y seedwork | Solicitud, política, evaluación, agregación raíz, eventos y puertos implementados. |
| Verificación local | 203 pruebas aprobadas, incluidas 36 de integración con PostgreSQL; lint, formato, tipado y distribución comprobados. HTTP real verificado en 01. |
| Contratos internos | Registro, evaluación, solicitud lista y rechazada, con versiones y datos inmutables. |
| Handlers y bus local | Registro idempotente, evaluación inicial única, transición y despacho por consumidor comprobados con UoW en memoria y SQL; las entregas avanzan explícitamente en pruebas. |
| Persistencia | PostgreSQL, Alembic, ORM/mapeadores, inbox y outbox con reservas recuperables. |
| Pulsar y CQRS | Pendientes de 05–06. CQRS sigue siendo obligatorio. |

Los resultados corresponden a la corrida registrada del 12 de septiembre de 2026. [Evidencia del plan 01](docs/plans/evidencia-01-base-tecnologica.md) · [Evidencia del plan 02](docs/plans/evidencia-02-modelo-dominio-seedwork.md) · [Evidencia del plan 03](docs/plans/evidencia-03-comandos-eventos-internos.md) · [Evidencia del plan 04](docs/plans/evidencia-04-sqlalchemy-uow-outbox.md) · [Modelo de dominio](docs/modelo-dominio.md) · [Planes de construcción](docs/plans/README.md).

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

`.env.example` enumera las variables, pero no se carga automáticamente. Exportarlas en la terminal o configurarlas en el entorno de ejecución. No guardar credenciales reales en archivos versionados.

`create_app` acepta `Settings` y una factoría de base para pruebas. Lee el entorno al crear cada aplicación, sin configuración global cacheada. Si hay URL, el lifespan construye Engine/sessionmaker sin abrir conexiones y libera el Engine al cerrar, también ante excepciones. Cada invocación de `session_factory()` entrega una sesión independiente. Su propietario debe cerrarla; las UoW SQL controlan las transacciones. La API no ejecuta migraciones ni conecta todavía el flujo de negocio.

## Persistencia local

El entorno de 04 usa PostgreSQL 17.6, SQLAlchemy 2.0.52, psycopg 3.3.5 y Alembic 1.20.0. Compose publica exclusivamente en `127.0.0.1:55434`, con volumen propio y credenciales de laboratorio. Las dependencias Python están fijadas en `uv.lock`.

```bash
docker compose -f docker_compose.yaml up -d --wait
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

Los esquemas `solicitudes` y `reglas_partner` contienen tablas de sus módulos; `mensajeria` contiene inbox/outbox. `lectura` queda preparado y vacío para 06. Los datos compuestos y eventos se conservan en JSONB mediante mapeadores y formatos explícitos; identidad, referencia, estado y versión de solicitudes tienen columnas relacionales. El origen de evaluación se conserva separado del outbox. El modelo de dominio no es ORM.

`config/bootstrap.py:componer_flujo_sql` conecta los handlers; `config/persistencia.py` construye las UoW y configura destinos `laboratorio.<tipo_evento>`. `config/serializacion.py` selecciona los codecs de infraestructura propietarios. Los codecs conservan UUID y fechas en UTC, validan el formato 1 y reconstruyen los cuatro eventos. Los tópicos y contratos públicos de Pulsar se acuerdan en 05.

Cada entrega tiene identidad estable por evento/destino. `DespachadorOutbox.despachar_lote()` reserva un lote, llama al puerto `Publicador` fuera de la transacción de reserva y marca solo los acuses positivos. Un token vencido no permite actualizar la reserva de otro worker. El método ejecuta un lote a petición; todavía no existe un proceso continuo. `inspeccionar_outbox.py` muestra pendientes, antigüedad, intentos y errores sin modificar filas.

Para observar el recorrido con PostgreSQL y bus de laboratorio:

```bash
uv run --locked pytest tests/integracion/test_flujo_sql.py -v
```

Para detener el entorno preservando el volumen:

```bash
docker compose -f docker_compose.yaml stop
```

## Verificar

```bash
uv sync --locked
docker compose -f docker_compose.yaml up -d --wait
uv run --locked pytest tests -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests scripts migraciones
uv run --locked python scripts/verify_distribution.py
```

El script de distribución crea un entorno temporal con dependencias de producción del lockfile, construye sdist y wheel, reinstala ese wheel sin resolver otras dependencias y lo importa desde fuera del árbol fuente con Python en modo aislado. Elimina sus archivos temporales al terminar. Para generar artefactos conservables en `dist/`, ejecutar `uv build`.

La suite completa habilita `tests/unitarias`, `tests/api` y `tests/integracion`. Integración requiere PostgreSQL: crea una base temporal `partner_test_<uuid>`, aplica migraciones, limpia sus propias tablas entre casos y elimina esa base al terminar. El usuario SQL de pruebas necesita permiso de crear bases; nunca se truncan tablas de la base de desarrollo. `PARTNER_TEST_DATABASE_URL` permite cambiar la conexión administrativa de laboratorio; su valor predeterminado corresponde al Compose del repositorio. Si falta PostgreSQL, las pruebas fallan, sin skips. `tests/contratos` sigue sin casos y no representa cobertura de Pulsar. Las pruebas bloquean los puntos de conexión Python al verificar importación y lifespan; el cliente Pulsar nativo todavía no forma parte de la aplicación.

TestClient usa `httpx2`, requerido por la versión resuelta de Starlette; por ello sustituye al `httpx` inicialmente propuesto. Hay una advertencia visible de Starlette por el alias obsoleto `anyio.abc.BlockingPortal`. No se modifica código de terceros ni se suprime esa advertencia. Las deprecaciones originadas en el paquete propio hacen fallar pytest.

## Compatibilidad preliminar Pulsar

```bash
uv run --isolated --no-project --python 3.12.3 --with pulsar-client==3.13.0 python -c 'import importlib.metadata, platform, pulsar; print({"python": platform.python_version(), "system": platform.system(), "architecture": platform.machine(), "pulsar_client": importlib.metadata.version("pulsar-client"), "client_imported": callable(pulsar.Client)})'
```

Resultado local: Python 3.12.3, Linux x86_64, cliente 3.13.0 importado. Este ensayo usa un entorno independiente; Pulsar no es dependencia de producción y no se instancia un cliente ni se contacta un broker. En el plan 05 deben repetirse compatibilidad y ensayos de serialización/publicación/consumo con las versiones acordadas por el equipo.

## Organización

```text
src/solicitudes_partner/
  api/
    app.py
  config/
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

El siguiente paso es el [plan 05: Pulsar y contratos](docs/plans/05-pulsar-contratos.md). Después se implementarán CQRS y experimentación, según la [secuencia acordada](docs/plans/README.md).

El flujo completo se demuestra con `uv run --locked pytest tests/unitarias/aplicacion/test_flujo_interno.py -v`. Las pruebas avanzan explícitamente desde el registro confirmado hasta la evaluación y el resultado; incluyen reentregas y fallos antes y después de confirmar. Ese comando usa dobles, sin conexiones externas. La demostración SQL está en `tests/integracion/test_flujo_sql.py`.

Todavía no hay recepción de solicitudes por HTTP, transporte Pulsar automático, proyección CQRS ni experimentos de carga. El outbox SQL conserva los pendientes; el bus local sigue sin ser un transporte durable de producción. El publicador de pruebas simula el acuse, por lo que no demuestra recuperación del broker ni ACK real. Entrada y una porción de Reglas se agrupan explícitamente para la POC; sus dos módulos internos cuentan como **un servicio** dentro de los cuatro requeridos. Orquestación, Cotizaciones y Scoring quedan fuera de este repositorio.
