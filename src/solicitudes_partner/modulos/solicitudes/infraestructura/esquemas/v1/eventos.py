from pulsar.schema import Boolean, Integer, Record, String


class BooleanOpcional(Boolean):
    # Boolean.default() del SDK convierte None en False: conservar ausencia de aprobacion.
    # https://github.com/apache/pulsar-client-python/blob/v3.13.0/pulsar/schema/definition.py
    def default(self) -> None:
        return None


class SolicitudListaV1(Record):
    event_id = String(required=True)
    tipo = String(required=True)
    version_contrato = Integer(required=True)
    instante = String(required=True)
    correlacion = String(required=True)
    id_solicitud = String(required=True)
    version_solicitud = Integer(required=True)
    id_partner = String(required=True)
    referencia_externa = String(required=True)
    categoria = String(required=True)
    tipo_solicitud = String(required=True)
    aprobacion_previa = BooleanOpcional(required=False)
    tipo_red = String(required=True)
    id_politica = String(required=True)
    version_politica = Integer(required=True)
