from dataclasses import fields
from datetime import UTC
from uuid import UUID

from solicitudes_partner.modulos.solicitudes.aplicacion.vistas import (
    ActualizacionVista,
    VistaSolicitud,
)
from solicitudes_partner.modulos.solicitudes.dominio.eventos import (
    SolicitudPartnerListaParaAtencion,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.esquemas.v1.eventos import (
    SolicitudListaV1,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.esquemas.v1.lectura import (
    SolicitudLecturaV1,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.mapeadores import (
    actualizacion_desde_evento,
    cargar_vista,
    guardar_vista,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.serializacion import decodificar
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio
from solicitudes_partner.seedwork.infraestructura.serializacion import Documento

TIPO_LECTURA = "SolicitudDePartnerActualizada.v1"


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


def mensaje_lectura(documento: Documento) -> SolicitudLecturaV1:
    try:
        actualizacion = actualizacion_desde_evento(decodificar(documento))
    except (KeyError, TypeError) as error:
        raise ValueError("Documento no proyectable") from error
    return SolicitudLecturaV1(
        event_id=str(actualizacion.id_evento),
        tipo=TIPO_LECTURA,
        version_contrato=1,
        **guardar_vista(actualizacion.vista),
    )


def leer_mensaje(mensaje: SolicitudLecturaV1) -> ActualizacionVista:
    if mensaje.tipo != TIPO_LECTURA or mensaje.version_contrato != 1:
        raise ValueError("Contrato de lectura desconocido")
    documento = {campo.name: getattr(mensaje, campo.name) for campo in fields(VistaSolicitud)}
    return ActualizacionVista(UUID(mensaje.event_id), cargar_vista(documento))
