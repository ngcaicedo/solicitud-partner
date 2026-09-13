from datetime import UTC

from solicitudes_partner.modulos.solicitudes.dominio.eventos import (
    SolicitudPartnerListaParaAtencion,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.esquemas.v1.eventos import (
    SolicitudListaV1,
)
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio


def evento_integracion(evento: EventoDominio) -> SolicitudListaV1:
    if not isinstance(evento, SolicitudPartnerListaParaAtencion):
        raise ValueError("La integracion requiere una solicitud lista")
    evento.__post_init__()
    assert evento.evaluacion.tipo_red is not None
    return SolicitudListaV1(
        event_id=str(evento.id_evento),
        tipo="SolicitudDePartnerListaParaAtencion.v1",
        version_contrato=1,
        instante=evento.instante.astimezone(UTC).isoformat(),
        correlacion=str(evento.id_solicitud),
        id_solicitud=str(evento.id_solicitud),
        version_solicitud=evento.version_solicitud,
        id_partner=str(evento.datos.id_partner),
        referencia_externa=evento.datos.referencia_externa,
        categoria=evento.datos.categoria,
        tipo_solicitud=evento.datos.tipo.value,
        aprobacion_previa=evento.datos.aprobacion_previa,
        tipo_red=evento.evaluacion.tipo_red.value,
        id_politica=str(evento.evaluacion.id_politica),
        version_politica=evento.evaluacion.version_politica,
    )
