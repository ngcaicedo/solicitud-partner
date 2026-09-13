# Entrada de Solicitudes de Partner

Microservicio de Entrada de Solicitudes de Partner de Hogar de los Alpes, para el canal B2B2C. Su construcción parte de dos módulos internos: Solicitudes de Partner y Reglas de Partner, con arquitectura hexagonal y seedwork local.

## Estado actual

Los **planes 01–03 están implementados y verificados localmente**. El servicio cuenta con base técnica, modelos de dominio y el flujo interno de registro, evaluación y transición mediante handlers y un bus local. La persistencia de negocio todavía se sustituye por dobles de prueba.

| Componente | Estado |
|---|---|
| Paquete Python y entorno uv | Instalación reproducible con `uv.lock`. |
| FastAPI | Factoría de aplicación y `GET /health/live`. |
| SQLAlchemy y psycopg | Factoría de Engine y sesiones independientes, sin conexión durante el arranque. |
| Módulos y seedwork | Solicitud, política, evaluación, agregación raíz, eventos y puertos implementados. |
| Verificación local | 154 pruebas aprobadas; lint, formato, tipado y distribución comprobados. HTTP real verificado en 01. |
| Contratos internos | Registro, evaluación, solicitud lista y rechazada, con versiones y datos inmutables. |
| Handlers y bus local | Registro idempotente, evaluación inicial única, transición y despacho por consumidor comprobados con UoW en memoria. |
| Persistencia, Pulsar y CQRS | Pendientes de 04–06. CQRS sigue siendo obligatorio. |

Los resultados corresponden a la corrida registrada del 12 de septiembre de 2026. [Evidencia del plan 01](docs/plans/evidencia-01-base-tecnologica.md) · [Evidencia del plan 02](docs/plans/evidencia-02-modelo-dominio-seedwork.md) · [Evidencia del plan 03](docs/plans/evidencia-03-comandos-eventos-internos.md) · [Modelo de dominio](docs/modelo-dominio.md) · [Planes de construcción](docs/plans/README.md).

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

`create_app` acepta `Settings` y una factoría de base para pruebas. Lee el entorno al crear cada aplicación, sin configuración global cacheada. Si hay URL, el lifespan construye Engine/sessionmaker sin abrir conexiones y libera el Engine al cerrar, también ante excepciones. Cada invocación de `session_factory()` entrega una sesión independiente. Su propietario debe cerrarla; las UoW futuras controlarán las transacciones. No se crean tablas ni se ejecutan migraciones.

## Verificar

```bash
uv sync --locked
uv run --locked pytest tests/unitarias tests/api -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests scripts
uv run --locked python scripts/verify_distribution.py
```

El script de distribución crea un entorno temporal con dependencias de producción del lockfile, construye sdist y wheel, reinstala ese wheel sin resolver otras dependencias y lo importa desde fuera del árbol fuente con Python en modo aislado. Elimina sus archivos temporales al terminar. Para generar artefactos conservables en `dist/`, ejecutar `uv build`.

Las suites `tests/unitarias` (incluidos `dominio/` y `aplicacion/`) y `tests/api` son las habilitadas en este incremento. `tests/integracion` y `tests/contratos` reservan la estructura futura; aún no contienen casos y no representan cobertura. Las pruebas bloquean los puntos de conexión Python al verificar importación y lifespan; el cliente Pulsar nativo todavía no forma parte de la aplicación.

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

El siguiente paso es el [plan 04: persistencia confiable](docs/plans/04-sqlalchemy-uow-outbox.md). Después se implementarán Pulsar, CQRS y experimentación, según la [secuencia acordada](docs/plans/README.md).

El flujo completo se demuestra con `uv run --locked pytest tests/unitarias/aplicacion/test_flujo_interno.py -v`. Las pruebas avanzan explícitamente desde el registro confirmado hasta la evaluación y el resultado; incluyen reentregas y fallos antes y después de confirmar. No se conectan a PostgreSQL, Pulsar ni Docker.

Todavía no hay recepción de solicitudes por HTTP, outbox durable, persistencia de negocio o experimentos de carga. El bus local no es un worker de producción y no conserva mensajes tras reiniciar; los dobles tampoco implementan control concurrente. Entrada y una porción de Reglas se agrupan explícitamente para la POC; sus dos módulos internos cuentan como **un servicio** dentro de los cuatro requeridos. Orquestación, Cotizaciones y Scoring quedan fuera de este repositorio.
