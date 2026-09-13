# Auditoría del plan 02 — Modelos de dominio y seedwork

Fecha: 2026-09-12. Objeto: [plan 02](02-modelo-dominio-seedwork.md), versión local de 28 líneas. Base Git del servicio: `d705cf6`; existen cambios locales y planes sin seguimiento. Se auditó el contenido del árbol de trabajo, no solamente el commit.

Actualización posterior: por solicitud de Nicolás, se reemplazó el objetivo referido a tutoriales por el trabajo concreto y se incorporaron H1–H4 a las tareas y criterios de cierre del plan 02. Se añadieron la matriz de cuatro eventos y sus versiones, las defensas del agregado ante evaluaciones ajenas/repetidas/contradictorias, la pertenencia y ausencia de política, y la reconstrucción sin eventos nuevos. Los hallazgos quedan atendidos documentalmente; su validación mediante código y pruebas permanece pendiente. El dictamen, las referencias de líneas y los resultados de pruebas siguientes corresponden a la auditoría original, no a una ejecución del plan ajustado.

Actualización de idioma: Nicolás sustituyó la convención anterior por identificadores propios en español y el vocabulario del Event Storming. Se eliminó el glosario de traducción del plan 02 y se actualizaron los modelos, eventos, estados y la convención documental común. Las referencias al acuerdo anterior en esta auditoría se conservan como antecedentes históricos.

Actualización de política aprobada por Nicolás: el plan 02 determina la red general de HdA o la red homologada del partner, con fundamento en las páginas 9 y 13 del enunciado. Se retiraron la admisibilidad por categorías y el rechazo empresarial de este recorte; ahora hay tres eventos y la transición `RECIBIDA → LISTA_PARA_ATENCION`. Se ajustaron H1–H4 para conservar condiciones de red, trazabilidad, invariantes y reconstrucción. Se sincronizaron los planes 03–06 y 08. Las menciones siguientes a cuatro eventos, categorías y rechazos describen la versión histórica auditada, no el plan vigente. Solo se modificó documentación.

Actualización vigente — rechazo sencillo solicitado por Nicolás: se conserva la política de red y se incorpora el rechazo de siniestros con aprobación previa declarada como falsa, con motivo `APROBACION_PREVIA_REQUERIDA`. Las instalaciones no requieren esa aprobación. La omisión del campo obligatorio es error de validación; una política inexistente o inválida es error de configuración. Se restablecen `RECHAZADA` y su evento, se ajustan H1–H4 y los planes posteriores, sin implementar código. Esta decisión sustituye la retirada del rechazo indicada en la nota anterior.

## Dictamen

El plan está alineado con las decisiones aprobadas. Recomiendo conservar su alcance y secuencia, pero precisar cuatro criterios antes de cerrar su implementación. Son vacíos de especificación y verificación, no bugs reproducidos: los paquetes de dominio y seedwork todavía contienen únicamente archivos `__init__.py` vacíos.

No hace falta rediseñar el servicio, añadir otro módulo ni implementar anticipadamente Pulsar o CQRS. Sí hace falta que el modelo producido por este incremento pueda sostener los comportamientos ya exigidos en los planes 03–06.

## Fuentes y acuerdos recuperados

Se revisaron las cuatro conversaciones solicitadas:

- **Iniciar microservicio de partners** (`codex://threads/01a096fb-8fab-78c1-91b0-56a4053d8896`): construcción desde cero, CQRS obligatorio, seedwork local, organización de AeroAlpes y dos módulos internos. La respuesta de Nicolás «Si confirmemos, tiene logica» aprueba la agrupación de Entrada y una porción de Reglas para la POC. Las decisiones posteriores fijan carpetas en español e identificadores de código en inglés.
- **Revisa tutoriales de solución** (`codex://threads/01a096f0-75dc-7022-a3a7-17bb02184c4c`): preservar módulos/capas y modelos propios; evitar copiar publicación duplicada, UoW defectuosa, proyecciones no idempotentes y pruebas dependientes del broker.
- **Analiza POC de entrega 4** (`codex://threads/01a096c6-b4ec-7542-941f-2090d6ab95b6`): cuatro servicios persistentes y evidencia observable. Este repositorio representa uno. Orquestación crea y cierra trabajos; Scoring recibe el cierre, no el registro de la solicitud.
- **Audita el primer plan (2)** (`codex://threads/01a0978c-8344-7a00-8417-08cf173c6ebd`): base tecnológica implementada; presentación compartida solo cuando tenga usos concretos; retirada de GitHub del primer incremento y actualización del README.

El lector de tareas devolvió algunos turnos recientes vacíos. Se completó su lectura con los registros locales de esas dos conversaciones, exclusivamente mensajes del usuario y respuestas finales. Así se recuperaron la aprobación y los últimos ajustes, sin inferirlos de propuestas anteriores del asistente.

También se contrastaron el [índice vigente](README.md), planes 03–06, [auditoría anterior](auditoria-01-base-tecnologica.md), [evidencia del plan 01](evidencia-01-base-tecnologica.md), README y código actuales. La [arquitectura de entrega 2](../../../../entrega2/hogar_alpes_entrega_2/README.md), líneas 372–373, distingue recepción de solicitudes ya aprobadas y políticas versionadas del partner. La transcripción local `tutoriales/arquitectura-hexagonal.txt` respalda la separación entre modelo de dominio y persistencia y un seedwork ligero.

No se consultaron nuevamente NotebookLM, Coursera ni los repositorios externos. Sus conclusiones se usan como antecedentes de las conversaciones, no como verificaciones nuevas. No hay un grafo consultable en las raíces inspeccionadas; se usaron archivos y búsquedas.

## Hallazgos

### H1 — P2: el cierre de contratos no cubre explícitamente los eventos terminales ni su versión

**Evidencia:** plan 02, líneas 14 y 18. Se pide un evento por cambio válido, pero solo se detallan contratos de registro y evaluación. El [plan 06](06-cqrs-api.md), líneas 11–14, necesita motivos, política, fechas y versión por solicitud para proyectar sin consultar escritura. El [plan 05](05-pulsar-contratos.md), línea 17, requiere publicar la solicitud lista únicamente después de la transición.

**Riesgo:** cerrar 02 con eventos terminales que solo contienen ID y estado obligaría a ampliarlos después o a consultar tablas de escritura para completar la proyección. También queda sin distinguir la versión del agregado, la versión de política y la versión de esquema: cumplen funciones diferentes.

**Ajuste recomendado:** incluir en la matriz los cuatro hechos acordados: registro, evaluación, solicitud lista y solicitud rechazada. Documentar productor, consumidor previsto, propietario del contrato y datos mínimos. Definir cómo cambia la versión de solicitud y qué evento la transporta. Conservar identidad e instante del hecho; el sobre de transporte y el contrato público definitivo permanecen en 05.

**Cierre verificable:** ejemplos inmutables de los cuatro eventos permiten identificar la solicitud y describir el cambio; los terminales conservan la trazabilidad de evaluación necesaria para la lectura. Dos transiciones válidas tienen versiones coherentes y una transición inválida no produce evento. No se exige implementar el proyector ni fijar ahora Avro, tópicos o payload externo.

### H2 — P2: las defensas ante evaluaciones ajenas y contradictorias aparecen demasiado tarde

**Evidencia:** plan 02, líneas 12–15, solo enumera transiciones inválidas en general. El [plan 03](03-comandos-eventos-internos.md), líneas 15–16, exige aplicar el resultado mediante el agregado, rechazar resultados de otra solicitud y protegerse de una segunda decisión contradictoria; además excluye reevaluaciones.

**Riesgo:** implementar en 02 métodos que únicamente cambian el estado permitiría que las comprobaciones terminen exclusivamente en el handler de 03. Otro adaptador podría saltarse esas defensas, dejando un modelo que no protege sus invariantes.

**Ajuste recomendado:** trasladar a los criterios unitarios de 02 la correlación de la evaluación con la solicitud, una única decisión inicial y la prohibición de cambiar una decisión terminal. Definir el comportamiento de una repetición equivalente, sin duplicar eventos. La deduplicación por mensaje sigue perteneciendo al inbox de 04 y no reemplaza estas reglas.

**Cierre verificable:** una evaluación ajena no cambia estado ni eventos; una decisión contradictoria no revierte el resultado; repetir la decisión equivalente no genera otro cambio empresarial. La prueba usa datos o contratos explícitos, sin importar el agregado de Reglas dentro del dominio de Solicitudes. El plan 03 verifica después el recorrido completo entre handlers.

### H3 — P2: la política de ejemplo carece de casos para pertenencia y ausencia

**Evidencia:** plan 02, líneas 15–17. La evaluación conserva una versión y la política admite categorías por partner, pero el cierre solo exige evaluación positiva/negativa y trazabilidad de versión.

**Riesgo:** una implementación podría evaluar la solicitud del partner A con una política de B y seguir pasando los dos casos propuestos. Tampoco se especifica si la ausencia de política es un rechazo de negocio o un error de configuración, que requeriría un tratamiento diferente en el consumidor futuro.

**Ajuste recomendado:** precisar identidad de partner, identidad/versionado de política y coherencia con la evaluación. Para esta POC, usar fixtures explícitos y estables. Recomiendo tratar la falta de política como error de configuración, sin fabricar una decisión favorable o un rechazo empresarial; cualquier elección diferente debe quedar documentada como regla de la demostración. El evaluador recibe datos y política, sin consultar repositorios ni reloj global.

**Cierre verificable:** categoría habilitada y no habilitada, política de otro partner, ausencia de política y conservación de su identidad/versión. Mutar la colección usada para construir una política o los motivos originales no altera una evaluación ya emitida. No se exige motor de reglas ni administración de políticas en este incremento.

La regla por categorías sigue siendo una hipótesis de laboratorio, como correctamente declara el plan. No debe reinterpretarse como aprobación de cobertura del siniestro. Los planes permiten avanzar con fixtures sin esperar el contrato público del equipo.

### H4 — P2: falta distinguir creación empresarial y reconstrucción desde persistencia

**Evidencia:** plan 02, líneas 13–14, exige eventos pendientes y evento inicial, pero no define reconstrucción del agregado. El [plan 04](04-sqlalchemy-uow-outbox.md), líneas 12 y 23, exige mappers separados y mapeo de ida y vuelta.

**Riesgo:** si el único camino de construcción registra automáticamente una solicitud nueva, el mapper podría volver a producir el evento de registro al cargar una solicitud existente. Eso comprometería el flujo aun cuando el relay e inbox fueran correctos.

**Ajuste recomendado:** separar creación y reconstrucción como comportamientos del modelo, sin imponer una fábrica o jerarquía adicional. Reconstruir conserva identidad, estado y versión y comienza sin eventos pendientes. Definir además cómo se consultan/retiran los eventos sin compartir una lista global ni permitir modificar su contenido desde fuera.

**Cierre verificable:** crear genera el evento inicial; reconstruir una solicitud válida en estado recibido o terminal no genera eventos; dos agregados no comparten pendientes; fallar una transición no modifica estado ni pendientes. Es una prueba pura con datos de estado, no Event Sourcing ni una prueba SQL. La coordinación con commit/rollback queda en 04.

## Precisiones menores

- **Igualdad:** la línea 13 puede leerse ambiguamente. Explicitar identidad para entidades y agregados, e igualdad por atributos para objetos valor. Probar ambos comportamientos; evitar que la comparación accidental de todos los campos determine si dos entidades representan la misma identidad.
- **Puertos:** 02 crea puertos mínimos de Repository/UoW y 03 vuelve a indicar que los implementa. Aclarar que 03 utiliza/extiende los contratos y crea dobles. UoW corresponde a aplicación; las interfaces específicas permanecen con sus propietarios. No crear interfaces genéricas sin consumidores reales.
- **Aislamiento:** la prueba existente `tests/unitarias/test_isolation.py` acredita importación/lifespan sin conexiones, no la independencia entre capas de dominio. El cierre de 02 debe comprobar ambas cosas por separado. Un dominio que importa FastAPI sin abrir sockets todavía incumple el plan. No basar la comunicación entre módulos únicamente en buscar cadenas de imports: eso se demuestra funcionalmente en 03.
- **CI:** aún aparecen menciones en planes posteriores. La conversación retiró GitHub del primer incremento; esas menciones no justifican reintroducir un workflow durante 02. Su eventual alcance debe revisarse al ejecutar esos planes.

## Lo que debe conservarse

| Decisión | Resultado de la auditoría |
|---|---|
| Solicitudes y Reglas con capas propias | Coherente con la agrupación aprobada y los tutoriales. |
| Seedwork local y ligero | Correcto; no trasladar políticas ni contratos concretos al seedwork. |
| Evaluación como registro inmutable, si basta | Válido; justificar invariantes e identidad no exige inventar otro agregado complejo. |
| Estados empresariales separados del outbox | Correcto; publicar no constituye otra etapa de negocio. |
| CQRS obligatorio en 06 | Correcto diferir implementación y preparar ahora los hechos necesarios. |
| Presentación compartida diferida | Coherente con el último acuerdo; no falta una carpeta obligatoria en 02. |
| Sin Event Sourcing, Saga, BFF ni otros servicios | Mantiene el alcance acordado. |
| Red → Green → Refactor | Apropiado para los modelos; los tests deben proteger comportamiento y no solo estructura. |

## Verificación realizada y alcance de la entrega

Se ejecutó `uv run --locked pytest tests/unitarias tests/api -q`: **14 passed, 1 warning**. La advertencia de Starlette sobre `BlockingPortal` coincide con la documentada previamente. Esta corrida verifica la base del plan 01; no demuestra reglas, modelos ni contratos del plan 02, todavía ausentes.

Se verificaron las referencias locales del informe. No se ejecutaron PostgreSQL, Pulsar, experimentos, lint o typecheck: no se modificó código. Solo se añadió esta auditoría; los planes originales permanecen intactos. No se hizo commit ni push.

Recomendación: precisar H1–H4 dentro del plan 02 y mantener la secuencia actual. No hace falta resolver anticipadamente los acuerdos externos de integración para construir y probar el dominio con fixtures explícitos.
