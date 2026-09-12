# 01 — Base tecnológica y pruebas unitarias

Estado: implementado y verificado localmente; CI configurada, ejecución remota pendiente. Dependencias: ninguna. [Evidencia y límites del cierre](evidencia-01-base-tecnologica.md).

Ajuste durante implementación: TestClient de la versión resuelta de Starlette requiere `httpx2`, que sustituye al `httpx` inicialmente propuesto. El tipado incluye también `scripts` y CI usa las variantes `uv run --locked` de los comandos siguientes.

## Objetivo

Entregar un paquete Python instalable y reproducible, una aplicación FastAPI comprobable sin servicios externos y la base técnica para persistencia con SQLAlchemy. Este primer plan no implementa todavía el flujo del partner.

## Decisiones

| Pieza | Decisión inicial | Motivo |
|---|---|---|
| Python | 3.12 como candidato; fijarlo tras comprobar instalación e importación de una versión candidata del cliente Pulsar en las plataformas de desarrollo y CI | Evitar incompatibilidad tardía de wheels |
| uv | Gestión de Python, dependencias, entorno y lockfile | Un flujo reproducible de desarrollo y CI |
| FastAPI | Factoría `create_app`; composición y dependencias explícitas | Sustituir colaboradores en tests |
| SQLAlchemy | API 2.x; modelos ORM separados del dominio | Preservar aislamiento del modelo de negocio |
| Acceso SQL | Session síncrona por unidad de trabajo; endpoints con I/O síncrono declarados como `def` | Inicio sencillo, sin bloquear el event loop con SQL síncrono |
| PostgreSQL | Driver psycopg desde el plan 01; servidor y pruebas SQL reales desde el plan 04 | Verificar la factoría sin conexión y después unicidad y transacciones reales |
| Tests | pytest; httpx/TestClient para pruebas del adaptador HTTP | Dominio y aplicación aislados; HTTP probado en proceso |
| Calidad | Ruff y mypy | Lint, formato y tipado verificables |
| Migraciones | Alembic desde el plan 04 | Esquema versionado |

El Engine y el pool pueden vivir durante el proceso. Una Session no se comparte globalmente ni entre peticiones, threads o entregas de mensajes. No conectar a la base ni al broker al importar módulos. El commit pertenece a la UoW, no a cada repositorio ni al cierre tardío de una dependencia HTTP.

## Estructura objetivo

```text
pyproject.toml
uv.lock
.python-version
.env.example
README.md
src/solicitudes_partner/
  api/
  modulos/
    solicitudes/{aplicacion,dominio,infraestructura}/
    reglas_partner/{aplicacion,dominio,infraestructura}/
  seedwork/{aplicacion,dominio,infraestructura}/
  config/
tests/
  unitarias/
  api/
  integracion/
  contratos/
docs/plans/
```

Las carpetas de módulos, capas y suites se nombran en español, sin tildes y con `snake_case`, según la [convención común de los planes](README.md#convención-de-nombres-para-todos-los-planes). Se conservan las convenciones técnicas `src`, `api`, `config`, `seedwork` y `tests`, y la ruta documental ya acordada `docs/plans`. Los identificadores de clases y funciones permanecen en inglés.

Crear paquetes reales mínimos; las llaves del árbol son abreviación documental. No generar clases vacías para completar carpetas. Seedwork se implementa incrementalmente en el plan 02.

## Trabajo

1. Inspeccionar la carpeta existente y conservar los planes. Antes de fijar Python, comprobar en un entorno limpio la instalación e importación de una versión candidata del cliente Pulsar. Registrar Python, cliente, sistema operativo, arquitectura, comandos y resultados para desarrollo y CI; si comparten plataforma, indicar esa equivalencia. Esta comprobación no requiere broker ni demuestra compatibilidad de esquemas. Crear `pyproject.toml` con layout `src`, configuración de empaquetado y versión de Python verificada.
2. Incorporar FastAPI, Uvicorn, SQLAlchemy, psycopg y configuración de entorno. Añadir pytest, httpx, Ruff y mypy al grupo de desarrollo. Resolver versiones compatibles con uv y generar el lockfile; no escribirlo a mano. Conservar la versión candidata de Pulsar y la evidencia del paso anterior para repetir la comprobación al incorporarlo en el plan 05.
3. Configurar pytest, clasificación de suites, Ruff y mypy. Registrar en README los comandos canónicos y en CI la sincronización con lockfile.
4. Red: test HTTP que exige `GET /health/live` con respuesta 200 y cuerpo estable; test de creación de dos aplicaciones independientes sin estado de overrides compartido. Añadir una prueba aislada de importación, creación, inicio y cierre de la aplicación sin variables obligatorias de PostgreSQL/Pulsar, con los puntos de conexión externa vigilados para que cualquier intento haga fallar el test.
5. Green: implementar factoría y endpoint de liveness. Liveness solo refleja que el proceso responde; readiness de infraestructura llegará después.
6. Configurar la factoría de Engine/sessionmaker SQLAlchemy con dialecto y driver explícitos. Probar su construcción real con psycopg instalado, una URL PostgreSQL de prueba y sin servidor disponible: crear sesiones distintas y liberar los recursos sin ejecutar SQL ni abrir conexiones. Vigilar el punto de conexión para detectar intentos accidentales. Las pruebas de transacciones SQL reales y de UoW pertenecen al plan 04.
7. Permitir reemplazar dependencias en tests; limpiar overrides al terminar. Probar con dobles que la composición libera los recursos que posee también ante excepciones y no comparte colaboradores entre aplicaciones. No inicializar PostgreSQL/Pulsar desde tests unitarios o desde el startup de la aplicación de pruebas. Los dobles acreditan el ciclo de vida de la composición, no el comportamiento transaccional del motor.
8. Crear `.env.example` sin credenciales reales y `.gitignore` para entorno virtual, cachés, secretos y resultados temporales.
9. Documentar instalación, ejecución local y límites de lo implementado. Configurar CI inicial para unitarias, API aislada, lint y tipado.

## Verificación prevista

Una vez configuradas las herramientas, los comandos canónicos serán:

```bash
uv sync --locked
uv run pytest tests/unitarias tests/api -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

Registrar cuáles se ejecutaron y su resultado. Probar instalación limpia usando el lockfile y construir e instalar el paquete de forma no editable en un entorno limpio; comprobar su importación desde fuera del árbol fuente. Documentar los comandos exactos según el empaquetado elegido. Los tests HTTP en proceso verifican el adaptador, no prueban red ni servidor de producción.

Para comprobar manualmente el arranque:

```bash
uv run uvicorn solicitudes_partner.api.app:create_app --factory
```

Este proceso permanece en ejecución. Consultar `GET /health/live` desde otra terminal, registrar código y cuerpo, y detener el servidor con Ctrl+C. No incluir este comando como un check de CI que termina por sí mismo.

## Cierre

- Python seleccionado con evidencia de instalación e importación del cliente Pulsar candidato en las plataformas declaradas. Registrar versiones, comandos y resultados; publicación, consumo y esquemas se validan en el plan 05.
- Una prueba demuestra que importar, crear, iniciar y cerrar la aplicación no intenta conexiones externas ni requiere configuración de infraestructura. El test falla ante cualquier intento de conexión vigilado.
- `GET /health/live` devuelve 200 y el cuerpo acordado; dos aplicaciones conservan colaboradores y overrides independientes. Las pruebas aisladas pasan sin red, base o broker.
- Psycopg está declarado y bloqueado; la factoría real Engine/sessionmaker se construye sin conexión, produce sesiones distintas y permite liberar recursos. La composición libera los recursos que posee también ante excepciones. Esto no acredita persistencia, commit, rollback ni atomicidad.
- Instalación limpia con lockfile y construcción/instalación no editable comprobadas; el paquete se importa desde fuera del árbol fuente.
- Pruebas unitarias y API aislada, lint, formato y typecheck verdes en local y CI. Conservar los comandos ejecutados y sus resultados, sin presentar comprobaciones pendientes como aprobadas.
- README permite reproducir instalación, verificaciones, arranque y parada; distingue la evidencia de este incremento de las pruebas PostgreSQL/Pulsar posteriores.

## Documentación verificada el 2026-09-12

- [uv: proyectos y lockfile](https://docs.astral.sh/uv/guides/projects/): `pyproject.toml` declara dependencias y `uv.lock` conserva resoluciones exactas.
- [SQLAlchemy: Session](https://docs.sqlalchemy.org/en/20/orm/session_basics.html): delimitar sesión y transacción; no compartir Session concurrentemente.
- [FastAPI: pruebas](https://fastapi.tiangolo.com/tutorial/testing/): pytest y TestClient permiten probar HTTP en proceso.
- [FastAPI: overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/): sustitución explícita de dependencias en pruebas.

Reconsultar documentación de uv, Ruff, mypy, Alembic y del driver para la configuración exacta al ejecutar el plan.
