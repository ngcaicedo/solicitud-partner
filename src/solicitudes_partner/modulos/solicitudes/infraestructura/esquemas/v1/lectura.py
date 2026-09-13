from pulsar.schema import Integer, Record, String


class SolicitudLecturaV1(Record):
    event_id = String(required=True)
    tipo = String(required=True)
    version_contrato = Integer(required=True)
    id_solicitud = String(required=True)
    id_partner = String(required=True)
    referencia_externa = String(required=True)
    categoria = String(required=True)
    tipo_solicitud = String(required=True)
    estado = String(required=True)
    version_solicitud = Integer(required=True)
    creada_en = String(required=True)
    actualizada_en = String(required=True)
    resultado = String(required=False)
    motivo = String(required=False)
    tipo_red = String(required=False)
    id_politica = String(required=False)
    version_politica = Integer(required=False)
