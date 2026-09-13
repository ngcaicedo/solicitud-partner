# Plan de construcción — Entrada de Solicitudes de Partner

Fecha: 2026-09-12. Estado: planes 01–05 implementados y verificados localmente. Planes 06–08 pendientes. [Evidencia del plan 01](evidencia-01-base-tecnologica.md) · [Evidencia del plan 02](evidencia-02-modelo-dominio-seedwork.md) · [Evidencia del plan 03](evidencia-03-comandos-eventos-internos.md) · [Evidencia del plan 04](evidencia-04-sqlalchemy-uow-outbox.md) · [Evidencia del plan 05](evidencia-05-pulsar-contratos.md).

## Acuerdos que gobiernan la implementación

- Construcción desde cero en esta carpeta; entrega 3 es referencia histórica.
- Dominio de negocio: Atención de solicitudes de partner B2B2C.
- Un servicio desplegable con dos módulos: Solicitudes de Partner y Reglas de Partner. Cada módulo tiene Aplicación, Dominio e Infraestructura, siguiendo la organización de los tutoriales de AeroAlpes.
- Seedwork local, arquitectura hexagonal, DDD táctico, CQRS obligatorio y comunicación por eventos. Solicitudes y Reglas usan el bus interno con entrega durable; Pulsar transporta el evento público hacia consumidores externos independientes. El transporte separado del proyector se concreta en 06.
- La POC pequeña prueba recuperación, extensibilidad y escala de consumidores; no exige construir todo el ciclo de un Trabajo. Los reportes distinguen esos mecanismos de la funcionalidad empresarial y cobertura de escenarios originales.
- Agrupación de POC aprobada por Nicolás: Entrada y una porción de Reglas se despliegan juntas. La entrega 2 sí las describía como servicios independientes: esta agrupación es una adaptación explícita, no una propiedad ya existente del TO-BE.
- Las carpetas `dominio/` representan capas de modelo de negocio, no nuevos dominios empresariales. CQRS tampoco constituye un dominio adicional.
- FastAPI, SQLAlchemy, uv y pruebas unitarias forman parte del primer incremento.
- Carpetas, paquetes e identificadores propios de clases, funciones, variables, estados y eventos en español según la convención siguiente. Usar directamente el vocabulario del Event Storming en código y documentación, sin un glosario de traducción al inglés.
- Sin Event Sourcing. Estado relacional, outbox e inbox no equivalen a un event store.
- Este repositorio cuenta como uno de los cuatro servicios requeridos. Orquestación, Cotizaciones y Scoring pertenecen a los otros responsables.

## Convención de nombres para todos los planes

Las carpetas de módulos, capas y suites se nombran en español, sin tildes y con `snake_case`. Esta convención aplica a los ocho planes y al README del servicio que se creará en el plan 01.

| Elemento | Ruta desde la raíz del repositorio |
|---|---|
| Paquete del servicio | `src/solicitudes_partner/` |
| Solicitudes de Partner | `src/solicitudes_partner/modulos/solicitudes/` |
| Reglas de Partner | `src/solicitudes_partner/modulos/reglas_partner/` |
| Capas de cada módulo y del seedwork | `aplicacion/`, `dominio/`, `infraestructura/` |
| Seedwork local | `src/solicitudes_partner/seedwork/` |
| Pruebas | `tests/unitarias/`, `tests/api/`, `tests/integracion/`, `tests/contratos/` |

Se conservan los nombres técnicos `src`, `api`, `config`, `seedwork`, `tests` y la ruta acordada `docs/plans`. También se mantienen archivos convencionales como `README.md`, `pyproject.toml` y `uv.lock`. Los identificadores propios nuevos usan español sin tildes: `SolicitudPartner`, `registrar_solicitud` y `RECIBIDA`. Conservar los nombres impuestos por bibliotecas y herramientas y los nombres de los contratos públicos documentados por el servicio productor. Esta convención reemplaza el acuerdo anterior de identificadores en inglés; la base tecnológica ya implementada conserva por ahora sus nombres hasta una refactorización explícita. Los ejemplos de rutas, imports y comandos deben usar los paquetes anteriores.

## Secuencia

| Plan | Resultado | Dependencia |
|---|---|---|
| [01 — Base tecnológica](01-base-tecnologica.md) | Entorno uv, FastAPI, SQLAlchemy y pruebas aisladas | Ninguna |
| [02 — Modelo y seedwork](02-modelo-dominio-seedwork.md) | Dos modelos delimitados y contratos internos | 01 |
| [03 — Flujo interno](03-comandos-eventos-internos.md) | Registro, evaluación y resultado por eventos | 02 |
| [04 — Persistencia confiable](04-sqlalchemy-uow-outbox.md) | PostgreSQL, UoW, migraciones, outbox e inbox | 03 |
| [05 — Pulsar y contratos](05-pulsar-contratos.md) | Bus interno automático y publicación externa recuperable | 04 |
| [06 — CQRS y API](06-cqrs-api.md) | Proyección asíncrona, consultas y API del servicio | 05 |
| [07 — Integración y experimentos](07-integracion-experimentos.md) | Evidencia de idempotencia, recuperación y carga | 06 |
| [08 — Despliegue y sustentación](08-despliegue-sustentacion.md) | Ejecución reproducible y documentación de resultados | 07 |

Ejecutar en orden. Cada plan contiene trabajo, verificación y criterios de cierre. Marcar un plan completo únicamente al registrar evidencia real; no confundir comandos propuestos con comandos ejecutados.

## Reglas de ejecución

1. Para comportamiento no trivial: test que falla, implementación mínima y refactorización con tests verdes.
2. Pruebas unitarias sin PostgreSQL, Pulsar, Docker ni red. Pruebas de integración separadas y obligatorias en su pipeline; no ocultar infraestructura ausente con skips que vuelvan verde la validación completa.
3. Antes de cada commit o push solicitado: suite completa habilitada, lint y typecheck. No hacer commit o push por ejecutar estos planes.
4. No compartir entidades ORM ni agregados entre módulos. Solo contratos explícitos e identificadores.
5. Un evento entre contextos conserva semántica de integración aunque los contextos se desplieguen juntos. Para la demostración académica distinguir eventos del dominio de Solicitudes, reacción de Reglas mediante contrato interno y evento publicado a otros servicios; el transporte no determina por sí solo la categoría.
6. Verificar documentación oficial y versiones reales al implementar cada integración. La selección de versiones exactas queda registrada en `uv.lock` durante el plan 01 y se extiende en planes posteriores.

## Evidencia y referencias

- Conversación de tutoriales: `codex://threads/01a096f0-75dc-7022-a3a7-17bb02184c4c`.
- Conversación de POC: `codex://threads/01a096c6-b4ec-7542-941f-2090d6ab95b6`.
- [Análisis de entrega 4](../../../analisis-critico-plan-poc-v2.md).
- [Arquitectura de entrega 2](../../../../entrega2/hogar_alpes_entrega_2/README.md).
- [Blueprint anterior](../../../../entrega3/hogar-de-los-alpes-servicio-dddesacoplados/docs/ai/02-blueprint-entrega-3.md).
- [Flujo interno anterior](../../../../entrega3/hogar-de-los-alpes-servicio-dddesacoplados/docs/ai/08-plan-bloque-2.3.md).
- NotebookLM del curso: `31f2c92a-9e81-4ca3-8d45-1ba9dbbb5ed1`. Usar sus respuestas para localizar fuentes; verificar inferencias en documentos originales. El notebook llamado Proyecto final corresponde a TravelHub y no fundamenta este servicio.

## Acuerdos externos aún necesarios

Entrada define el contrato público v1 en el plan 05: nombre del evento, payload, esquema, tópico, identificadores y datos para crear un Trabajo. Documenta ejemplos y versiones verificadas de cliente/broker; Los consumidores externos implementan ese contrato mediante suscripciones independientes, según el efecto que demuestren. No se requiere coordinación ni aprobación previa del compañero para definirlo, implementarlo o cerrar 05. Los fixtures validan este contrato; no lo convierten en provisional. La infraestructura compartida y los experimentos grupales conservan sus dependencias operativas posteriores, incluida la cobertura del marketplace y los consumidores históricos de extensibilidad. Estos puntos no autorizan construir otros servicios en este repositorio.
