# 03 — Comandos y comunicación interna

Estado: implementado y verificado localmente. [Evidencia de ejecución](evidencia-03-comandos-eventos-internos.md). Dependencia: 02. Ajustado tras la [auditoría del plan 03](auditoria-03-comandos-eventos-internos.md).

## Objetivo

Implementar el registro de solicitudes y el recorrido Solicitudes → Reglas → Solicitudes mediante handlers y publicación/suscripción. Verificar el comportamiento con repositorios, unidades de trabajo y entregas en memoria, usando los modelos y contratos implementados en 02.

Cada módulo conserva sus datos y controla su propia ejecución. El comando confirma recepción sin esperar evaluación ni proyección. Este incremento demuestra comunicación funcional; persistencia durable y mensajería distribuida pertenecen a 04–05, y CQRS con API de negocio a 06.

## Trabajo

Antes de implementar los handlers, trasladar las definiciones de eventos de dominio desde `contratos.py` a `dominio/eventos.py` de su módulo propietario. En Solicitudes: `SolicitudPartnerRegistrada`, `SolicitudPartnerListaParaAtencion`, `SolicitudPartnerRechazada` y su validación auxiliar. En Reglas: `ReglasDePartnerEvaluadas`. Eliminar los archivos `contratos.py`; importar los eventos directamente desde `dominio/eventos.py` y las enumeraciones desde `dominio/objetos_valor.py` de su propietario. Actualizar imports internos, pruebas, verificación de distribución y documentación del modelo; preservar campos, validaciones, versiones e identidad de los eventos. Esta reorganización del código de 02 se ejecuta como parte de 03.

1. Extender los puertos existentes, sin crear otro Repository/UoW paralelo. Añadir búsqueda de Solicitudes por partner/referencia y de evaluación inicial por solicitud en sus repositorios propietarios. Definir UoW específicas de aplicación con acceso solo a repositorios de su módulo, un mecanismo común para registrar salidas y puertos de reloj, generador de IDs y publicación/suscripción. Componer dependencias explícitas desde `config/bootstrap.py` mediante `componer_flujo`, sin singletons ni conexiones durante importación.
2. Red: una confirmación fallida no deja estado parcial ni eventos entregables. Green: dobles de UoW con estado aislado por ejecución, confirmación conjunta de cambios y salidas, y descarte al revertir o salir sin confirmar. No basta contar llamadas a rollback: las instancias modificadas dentro de la UoW no deben mutar el almacenamiento confirmado. Probar creación y actualización, incluidas las mutaciones de `SolicitudPartner.aplicar_evaluacion`.
3. Red: registrar datos válidos confirma una solicitud `RECIBIDA`, versión 1, y su evento; devuelve una confirmación antes de entregar eventos. Green: `RegistrarSolicitudPartner`, su handler y `ConfirmacionRegistroSolicitud`. La respuesta contiene el ID de la solicitud y el indicador `recepcion_confirmada`; no representa el estado actual del negocio ni devuelve el agregado. Usar `DatosSolicitud` y `SolicitudPartner.registrar` sin duplicar sus validaciones.
4. Red: misma clave partner/referencia y datos equivalentes devuelve el ID original sin crear ni modificar hechos, incluso si la solicitud ya está lista o rechazada; datos diferentes generan conflicto. Green: comparar exactamente los datos de negocio validados: partner, referencia, categoría, tipo y aprobación previa. Excluir IDs y tiempos generados por el servidor; no normalizar mayúsculas ni espacios. Cambiar aprobación en una instalación también cambia el contenido conservado, aunque no cambie su evaluación. Probar cada campo y la reutilización de referencia entre partners distintos. La protección concurrente durable llegará en 04.
5. Red: entregar un registro nuevo a Reglas confirma evaluación y salida con política/versión, resultado y red o motivo. Green: el handler obtiene la política de su repositorio, llama al evaluador puro existente, guarda `EvaluacionReglasPartner` y registra explícitamente `evaluacion.evento` como salida. No convertir esa entidad en agregado ni reconstruir el evento con otro ID o instante.
6. Red: repetir un registro ya evaluado no crea una segunda evaluación ni otro evento, aunque cambie o desaparezca la política actual. Green: buscar primero la evaluación inicial y conservar la asociación con los datos del registro de origen para detectar entradas incompatibles. Una repetición equivalente termina sin efectos; una entrada incompatible genera conflicto y conserva el resultado inicial. La comparación incluye identidad, instante y datos del registro original. No consultar de nuevo la política para una repetición ya confirmada. Si nunca se confirmó la evaluación por error de configuración, un intento tras corregir la política sí puede evaluarla. No implementar reevaluaciones; inbox durable y unicidad concurrente quedan en 04.
7. Red: entregar el resultado a Solicitudes confirma la transición y el evento terminal correspondiente. Green: cargar su agregado por ID, aplicar el contrato mediante `aplicar_evaluacion`, guardar y registrar sus pendientes como salidas. Una solicitud inexistente genera un error explícito sin crearla. Una evaluación ajena, inválida o diferente de la inicial no cambia estado ni salidas. Repetir la evaluación original no cambia versión, fecha, evaluación ni eventos. Conservar las defensas del agregado y no recalcular la política en este handler.
8. Red: el cableado de publicación/suscripción completa el recorrido, permite consumidores adicionales y despacho paso a paso. Green: bus local con cola de entregas por evento y consumidor, suscripciones explícitas y control de avance; publicar no ejecuta recursivamente handlers. Variar el orden de suscripción de un observador independiente no cambia el resultado empresarial.
9. Red: falla un consumidor y permanecen identificadas su entrega fallida y las pendientes, sin deshacer pasos confirmados ni repetir entregas ya completadas al reanudar. Green: detener el despacho, propagar el error y conservar la entrega fallida al frente hasta un reintento explícito. Un evento sin suscriptores queda observable como salida sin destinatarios; no dispara un handler implícito. El bus conserva este estado solo durante el proceso de prueba. Reintentos automáticos, DLQ y recuperación tras reinicio se implementan en 05.
10. Red: falla la confirmación de cada uno de los tres handlers. Green: cada ejecución usa su propia UoW; ninguna entrega salidas no confirmadas. Reglas fallida conserva el registro anterior; aplicación de resultado fallida conserva la evaluación anterior. La confirmación solo se devuelve después de confirmar el registro y no depende del drenaje de la cola. Mantener los IDs e instantes de los hechos confirmados al trasladarlos y reentregarlos.
11. Refactorizar con pruebas verdes y respetar la organización siguiente. Registrar evidencia de Red → Green → Refactor, recorrido, repeticiones y fallos; ejecutar las verificaciones locales documentadas en el README. No marcar completo el incremento solo por haber actualizado este documento.

## Fronteras de ejecución y salidas

Hay tres unidades de trabajo independientes:

| Ejecución | Datos propios | Salida confirmada |
|---|---|---|
| Registrar solicitud | Solicitud en versión 1 | `SolicitudPartnerRegistrada` |
| Evaluar registro | Evaluación inicial y asociación con registro de origen; lectura de política | `ReglasDePartnerEvaluadas` |
| Aplicar evaluación | Solicitud en versión 2 | `SolicitudPartnerListaParaAtencion` o `SolicitudPartnerRechazada` |

Cada UoW prepara cambios y mensajes de salida y los confirma juntos en el almacenamiento falso. Solo después pueden trasladarse esas salidas al bus, conservando el contrato original. La composición permite avanzar explícitamente esa transferencia y el despacho durante las pruebas. Los handlers no llaman a otros handlers ni drenan el bus.

La UoW común ofrece el mecanismo de registrar salidas; las específicas añaden los repositorios de su módulo. Solicitudes aporta pendientes del agregado y Reglas aporta `evaluacion.evento`. Retirar pendientes no puede perder la salida de una ejecución confirmada ni hacer entregable una ejecución fallida. Esta coordinación en memoria prepara la sustitución por outbox en 04; no implementa tabla outbox, serialización o relay ni garantiza sobrevivir al cierre del proceso.

## Organización de archivos

Rutas desde la raíz del repositorio. Extender archivos existentes cuando se indica; crear únicamente archivos con responsabilidad y contenido reales. Mantener la [convención común de nombres](README.md#convención-de-nombres-para-todos-los-planes) y la distribución del dominio fijada en 02, con el traslado de eventos especificado en este incremento.

| Ubicación | Archivo | Responsabilidad |
|---|---|---|
| `src/solicitudes_partner/modulos/solicitudes/aplicacion/` | `comandos.py` | Comando inmutable `RegistrarSolicitudPartner`; intención de registro con sus datos de entrada. |
| Misma ubicación | `confirmaciones.py` | `ConfirmacionRegistroSolicitud`, sin entidad de dominio ni estado final de evaluación. |
| Misma ubicación | `excepciones.py` | Conflicto de registro y solicitud inexistente; errores de aplicación sin códigos HTTP. |
| Misma ubicación | `unidad_trabajo.py` | Puerto específico con repositorio de Solicitudes y el mecanismo común de salidas. |
| `src/solicitudes_partner/modulos/solicitudes/aplicacion/handlers/` | `registrar_solicitud.py` | Idempotencia del comando, creación, confirmación de la UoW y respuesta de registro. |
| Misma ubicación | `aplicar_evaluacion.py` | Cargar solicitud, invocar su transición, guardar y preparar salidas. |
| `src/solicitudes_partner/modulos/reglas_partner/aplicacion/` | `unidad_trabajo.py` | Puerto específico con repositorios de políticas y evaluaciones. |
| Misma ubicación | `excepciones.py` | Conflicto de registro frente a una evaluación inicial existente. Reutilizar `ErrorConfiguracionPolitica` desde dominio. |
| `src/solicitudes_partner/modulos/reglas_partner/aplicacion/handlers/` | `evaluar_registro.py` | Comprobar repetición, obtener política, invocar evaluador y confirmar evaluación/salida. |
| `src/solicitudes_partner/modulos/solicitudes/dominio/` | `eventos.py` | Definiciones de registro, solicitud lista y rechazada, con su base y validación auxiliar; trasladadas desde `contratos.py`. |
| `src/solicitudes_partner/modulos/reglas_partner/dominio/` | `eventos.py` | Definición de `ReglasDePartnerEvaluadas` y sus validaciones, trasladada desde `contratos.py`. |
| `src/solicitudes_partner/modulos/solicitudes/dominio/` | `repositorios.py` existente | Añadir búsqueda por partner/referencia. |
| `src/solicitudes_partner/modulos/reglas_partner/dominio/` | `repositorios.py` existente | Añadir búsqueda de evaluación inicial por solicitud y operaciones para conservar/verificar su registro de origen; contratos explícitos, sin entidades ORM. |
| `src/solicitudes_partner/seedwork/aplicacion/` | `unidad_trabajo.py` existente | Ciclo común y puerto para registrar eventos de salida; sin repositorios de negocio concretos. |
| Misma ubicación | `reloj.py` | Puerto para obtener instantes con zona horaria. |
| Misma ubicación | `identificadores.py` | Puerto para generar identidades de solicitud, evaluación y eventos. |
| Misma ubicación | `bus_eventos.py` | Puerto mínimo de publicación/suscripción usado por la composición; no contiene rutas empresariales ni SDK. |
| `src/solicitudes_partner/seedwork/infraestructura/` | `bus_eventos_local.py` | Adaptador local con cola, entregas por consumidor y avance controlado para demostración y pruebas. Sin garantías durables. |
| `src/solicitudes_partner/config/` | `bootstrap.py` | Construir handlers con dependencias suministradas y suscribir registro → Reglas, evaluación → Solicitudes. No seleccionar dobles de prueba por defecto en producción. |
| `tests/unitarias/aplicacion/` | `datos.py` | Fixtures reutilizadas de comandos y escenarios; reutilizar datos de dominio cuando corresponda. |
| `tests/unitarias/aplicacion/dobles/` | `repositorios.py` | Repositorios falsos y asociaciones de origen, aislados por módulo. |
| Misma ubicación | `unidad_trabajo.py` | Almacenamiento confirmado, estado provisional, salidas e inyección de fallo de confirmación. |
| Misma ubicación | `reloj.py`, `identificadores.py` | Instantes e IDs deterministas para pruebas. |
| `tests/unitarias/aplicacion/` | `test_registro.py` | Registro, confirmación e igualdad/conflicto de contenido. |
| Misma ubicación | `test_evaluacion.py` | Política, evaluación, asociación con origen y repetición tras cambio de política. |
| Misma ubicación | `test_aplicacion_evaluacion.py` | Transición por handler, resultado ajeno, ausencia y repetición. |
| Misma ubicación | `test_unidad_trabajo.py` | Confirmación, reversión e independencia de estado y salidas. |
| Misma ubicación | `test_flujo_interno.py` | Recorrido completo mediante composición, bus y tres ejecuciones independientes; fallos por etapa. |
| `tests/unitarias/` | `test_bus_eventos_local.py` | Suscripciones, cola, observadores, errores, reintento explícito y entregas pendientes. |
| `docs/plans/` | `evidencia-03-comandos-eventos-internos.md` | Crear al ejecutar: evidencia real, comandos, resultados y límites. |

El bootstrap del flujo interno vive en `config/bootstrap.py`: `componer_flujo` construye los handlers y registra sus suscripciones con dependencias explícitas. Este archivo reemplaza a `config/composicion.py`; no se mantienen ambos. En 03 lo invocan las pruebas; la conexión con los puntos de entrada de producción corresponde a los incrementos posteriores.

Los `__init__.py` necesarios para los paquetes no contienen lógica ni activan recursos. No reunir comandos, confirmaciones, handlers y adaptadores en un `modelos.py`, `servicios.py` o `utils.py` genérico. El servicio puro de dominio de Reglas permanece en su `dominio/servicios.py`, donde ya tiene una responsabilidad definida.

Los eventos de dominio se definen y se importan directamente desde `dominio/eventos.py`, sin fachadas de reexportación. Las enumeraciones se definen y se importan desde `objetos_valor.py`. Entre módulos solo se permite importar los eventos compartidos y sus enumeraciones, nunca entidades, políticas, servicios o repositorios ajenos. Los esquemas de integración y adaptadores de transporte se implementarán en infraestructura durante 05; no duplicar ahora eventos ni enumeraciones. Los puertos comunes solo conocen mecanismos generales. Las pruebas conservan los modelos reales y sustituyen sus dependencias de I/O.

No crear bases `Comando`, `Consulta` o `Manejador` sin un uso concreto que aporte comportamiento o contrato común; este incremento no necesita despachador genérico de comandos ni queries. Tampoco crear `seedwork/presentacion`, mappers SQL ni DTO HTTP para completar la tabla: corresponden a usos posteriores.

## Demostración y cierre

Comprobar estado de repositorios falsos y eventos observables mediante handlers y el cableado real del bus; no sustituir la demostración por inspección de strings de imports.

| Etapa | Evidencia esperada |
|---|---|
| Registro confirmado antes de despachar | Una solicitud `RECIBIDA`, versión 1; confirmación devuelta; ningún registro de evaluación; evento de registro disponible. |
| Registro entregado a Reglas | Evaluación confirmada con política y resultado; evento de evaluación disponible; solicitud todavía recibida. |
| Evaluación entregada a Solicitudes | Versión 2, lista con red o rechazada con motivo; un evento terminal correspondiente. |
| Repetición equivalente | Mismos IDs, fechas y contenido confirmado; ninguna nueva evaluación, transición ni hecho de salida. |
| Error de configuración | Registro conservado; ninguna evaluación ni salida de resultado confirmada. |
| Fallo de confirmación | Ningún efecto parcial de ese paso; pasos anteriores confirmados conservados. |

El cierre exige:

- **H1 — Transacciones:** tres UoW independientes; salidas entregables y confirmación solo después de confirmar; fallos de cada etapa verificados con aislamiento efectivo de instancias.
- **H2 — Reentregas:** repetir el registro no reevalúa ni usa una política nueva; repetir el resultado no cambia versión ni genera evento. Datos de origen incompatibles no sustituyen la evaluación inicial.
- **H3 — Bus:** recorrido por suscripciones reales, observador adicional, variación de orden, fallo visible, pendientes conservadas y reintento explícito sin repetir entregas completadas.
- **H4 — Comando idempotente:** igualdad exacta de datos de negocio, conflicto por cada campo modificado, misma referencia en diferentes partners y confirmación estable tras estados terminales.
- **H5 — Salida de Reglas:** guardar la entidad real y registrar su `evento` original; misma identidad e instante hasta la entrega, sin exigirle pendientes de agregado.
- **Reglas empresariales:** red general y homologada; siniestro con aprobación falsa rechazado; instalación sin aprobación admitida. Omisión o tipo incorrecto de aprobación en siniestro falla antes del registro. Política ausente/ajena/inválida no produce evaluación y deja la solicitud recibida; tiene precedencia sobre el rechazo por aprobación falsa. Solicitud rechazada genera su evento y nunca el de solicitud lista.
- **Ubicación de eventos:** las cuatro clases se definen e importan desde el dominio propietario; no quedan fachadas `contratos.py`. Verificar que importar los módulos no genera ciclos y que el aislamiento permite solo mensajes y enumeraciones compartidos. Actualizar el modelo documentado y la verificación de distribución para las rutas nuevas.
- **Organización y evidencia:** archivos según responsabilidades de la tabla, modelos/contratos de 02 reutilizados, documentación del estado real y evidencia Red → Green → Refactor. Ejecutar pruebas, lint, formato, tipado y verificación de distribución con los comandos vigentes del README; no añadir workflows de GitHub en este incremento.

El bus local demuestra desacoplamiento funcional, pero no durabilidad, ejecución distribuida ni recuperación tras reinicio. Esas garantías permanecen en 04–05. La confirmación prepara CQS; la demostración CQRS completa sigue siendo obligatoria en 06. No hacer commit ni push por ejecutar el plan.
