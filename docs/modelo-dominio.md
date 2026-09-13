# Modelo de dominio implementado

El servicio contiene Solicitudes y Reglas de Partner, con modelos propios y contratos explícitos. El modelo se implementó en 02; el plan 03 incorporó handlers y bus local para ejecutar el recorrido, y trasladó los eventos a dominio conservando sus contratos públicos.

## Responsabilidades e invariantes

| Modelo | Responsabilidad e invariantes |
|---|---|
| `SolicitudPartner` | Agregación raíz por identidad. Registra la recepción, conserva una única evaluación y controla `RECIBIDA → LISTA_PARA_ATENCION | RECHAZADA`. La versión es 1 al recibir y 2 al resolver. |
| `DatosSolicitud` | Objeto valor inmutable: partner, referencia, categoría, tipo y aprobación declarada. Rechaza referencias/categorías vacías, identidades inválidas y tipos incorrectos. Un siniestro exige booleano explícito; `false` es válido como entrada. |
| `PoliticaPartner` | Configuración inmutable por partner y versión. Determina la red general o homologada. Se compara por todos sus atributos: representa una versión de la política, no una entidad mutable con administración propia. |
| `EvaluacionReglasPartner` | Entidad inmutable con identidad propia y contrato de resultado. No necesita una agregación compleja: no tiene transiciones ni entidades hijas. Su registro permite conservar qué solicitud y versión de política produjeron el resultado. |

Solicitud, caso y trabajo no son equivalentes. Este servicio conserva la solicitud; no crea casos operativos, selecciona proveedores, decide cobertura ni cierra trabajos.

## Reglas de la POC

1. La política debe existir, ser válida y pertenecer al partner; de lo contrario se produce `ErrorConfiguracionPolitica`, sin evaluación ni evento de resultado.
2. Un siniestro que declara `aprobacion_previa=False` produce `NO_ADMISIBLE` y `APROBACION_PREVIA_REQUERIDA`, sin red.
3. Un siniestro aprobado o una instalación producen `ADMISIBLE`, con `GENERAL_HDA` o `HOMOLOGADA_PARTNER` según la política y sin motivo de rechazo. Las instalaciones no requieren aprobación previa.

Son decisiones acotadas al laboratorio. La aprobación previa y las redes por partner se fundamentan en las páginas 9 y 13 del [enunciado](../../../Proyecto-202614-HogarDeLosAlpes.pdf); el campo booleano y las configuraciones específicas son elecciones de la POC. No se verifica la autenticidad de lo declarado ni se contacta a una aseguradora.

Los [datos de prueba](../tests/unitarias/dominio/datos.py) usan identificadores fijos y una fecha conocida. Las pruebas parametrizan ambas redes y aprobación verdadera, falsa o no aplicable. Estas configuraciones no son políticas reales. En 04 un script independiente permite cargar políticas ficticias explícitamente en PostgreSQL.

## Contratos y versiones

| Contrato | Propietario → consumidor previsto | Datos relevantes |
|---|---|---|
| `SolicitudPartnerRegistrada` | Solicitudes → Reglas y proyección | Identidad e instante del evento, solicitud, `datos` y versión 1. |
| `ReglasDePartnerEvaluadas` | Reglas → Solicitudes | Identidad de evento/evaluación, solicitud/partner, versión evaluada, identidad/versión de política, resultado y red o motivo. |
| `SolicitudPartnerListaParaAtencion` | Solicitudes → proyección e integración | Identidad e instante del evento, solicitud, `datos`, fecha de recepción, evaluación completa, estado listo y versión 2. |
| `SolicitudPartnerRechazada` | Solicitudes → proyección | Los mismos datos de trazabilidad, con estado rechazado, motivo y ninguna red. |

Los eventos concretos se definen y se importan directamente desde `dominio/eventos.py` de cada módulo. Esos mensajes son los contratos entre módulos; no hay archivos de reexportación `contratos.py`. El handler receptor de Solicitudes traduce `ReglasDePartnerEvaluadas` a su objeto valor `ResultadoEvaluacion`, con enumeraciones locales `Admisibilidad`, `TipoRedProveedores` y `MotivoRechazo`. Su dominio no importa tipos de Reglas. La recepción del registro en Reglas mantiene el contrato de Solicitudes y su `TipoSolicitud`; no se modifica esa frontera en este ajuste.

Los eventos finales contienen instantáneas inmutables en `datos` y `evaluacion`; esta última es el objeto propio `ResultadoEvaluacion`, no el evento de Reglas. Conserva la identidad y el instante del mensaje de origen para trazabilidad e idempotencia. Esto permite obtener referencia, categoría, fechas, política, red o motivo sin releer escritura. El adaptador de 05 transforma únicamente la solicitud lista al [contrato público Avro v1](contratos/README.md); los eventos de dominio conservan sus clases independientes del transporte.

La versión de solicitud identifica su cambio; la de política identifica las reglas aplicadas. La futura versión de esquema identifica el formato del mensaje. Los identificadores y fechas se reciben como argumentos y se preservan: ningún modelo genera IDs o consulta el reloj. Las fechas requieren zona horaria; la evaluación no puede preceder al registro ni seguir a la transición que la aplica.

## Uso del modelo

- `SolicitudPartner.registrar(...)` devuelve una solicitud recibida con un evento pendiente.
- `evaluar_solicitud(registro, politica, ...)` devuelve la evaluación con su evento estable; no persiste ni publica.
- `solicitud.aplicar_resultado_evaluacion(resultado, ...)` valida el contrato y cambia de estado. Una reentrega con idéntico contrato no cambia fechas, versión ni pendientes. Otra evaluación no reemplaza la inicial.
- `solicitud.eventos_pendientes` expone una tupla inmutable y `retirar_eventos()` la entrega y vacía los pendientes de esa instancia.
- `SolicitudPartner.reconstruir(...)` valida y carga datos de estado sin generar eventos. Puede reconstruir recibidas, listas y rechazadas. Esto no reproduce un historial ni implementa Event Sourcing.

La identidad y los atributos no admiten asignación directa. Los métodos de la agregación aplican cambios internos únicamente después de construir y validar el evento final. Un error no deja una transición parcial. La reconstrucción reutiliza las mismas invariantes; los futuros mappers no deben invocar `registrar` al cargar filas.

## Archivos por responsabilidad

| Ruta relativa a `src/solicitudes_partner/` | Responsabilidad |
|---|---|
| `modulos/solicitudes/dominio/eventos.py` | Registro, solicitud lista y rechazada; validación del resultado aplicado. |
| `modulos/reglas_partner/dominio/eventos.py` | Evaluación de reglas. |
| `modulos/solicitudes/dominio/entidades.py` | `SolicitudPartner`. |
| `modulos/solicitudes/dominio/objetos_valor.py` | Datos, tipo y estado de solicitud. |
| `modulos/reglas_partner/dominio/entidades.py` | `EvaluacionReglasPartner`. |
| `modulos/reglas_partner/dominio/objetos_valor.py` | Política, tipo de red, resultado y motivo. |
| `modulos/reglas_partner/dominio/servicios.py` | Evaluador puro. |
| `modulos/reglas_partner/dominio/excepciones.py` | Error de configuración de política. |
| `seedwork/dominio/entidades.py` | Entidad y agregación raíz. |
| `seedwork/dominio/objetos_valor.py` | Base de objetos valor. |
| `seedwork/dominio/eventos.py` | Base de eventos de dominio. |

Los eventos permanecen en `dominio/eventos.py` y los puertos específicos en `dominio/repositorios.py`. Se retiraron los archivos genéricos `modelos.py`; los imports internos apuntan a cada responsabilidad. Esta separación no añade reglas ni modifica el flujo.

## Seedwork y puertos

`Entidad` y `AgregacionRaiz` comparan por tipo e identidad; `ObjetoValor` proporciona la base de los valores inmutables. `EventoDominio` exige identidad e instante. Los pendientes pertenecen a cada agregación y no se comparten.

Los contratos `Repositorio`, `RepositorioSolicitudes`, `RepositorioEvaluaciones`, `RepositorioPoliticas` y `UnidadTrabajo` son puertos; sus adaptadores SQL se implementaron en 04. La UoW define entrada/salida de contexto, confirmación, reversión, preparación de entradas procesadas y registro de salidas. Los puertos específicos de aplicación exponen los repositorios de su módulo. Los dobles de 03 confirman estado y salidas mediante una copia aislada; 04 conserva esas fronteras con sesiones SQL independientes, inbox/outbox atómicos y recuperación de pendientes comprobada con PostgreSQL. Solicitudes permite buscar por partner/referencia; Reglas permite recuperar la evaluación inicial y el registro que la originó. Así se reconocen reentregas sin consultar una política nueva.

En 03 se añadieron `RegistrarSolicitudPartner`, `ConfirmacionRegistroSolicitud` y handlers separados para registrar, evaluar y aplicar resultados. La composición inyecta reloj, generador de IDs, fábricas de UoW y bus. El adaptador de integración se implementó en 05; las queries de 06 consultan exclusivamente la vista persistente del módulo Solicitudes. La [evidencia del plan 03](plans/evidencia-03-comandos-eventos-internos.md) enlaza las pruebas del flujo completo.

La [evidencia de 04](plans/evidencia-04-sqlalchemy-uow-outbox.md) registra persistencia del origen, concurrencia y reconstrucción sin eventos nuevos. Las UoW específicas declaran las restricciones SQL que admiten recuperación; los handlers reintentan esas colisiones como máximo tres veces, con rollback y sesión nueva. No se reintentan silenciosamente errores de configuración o contenido. La [evidencia de 05](plans/evidencia-05-pulsar-contratos.md) registra el despacho interno durable automático y el envío externo por Pulsar. La [evidencia de 06](plans/evidencia-06-cqrs-api.md) registra API y proyección CQRS persistente para recibidas, listas y rechazadas, con transporte propio y recuperación sin duplicados.
