from dataclasses import asdict
from datetime import UTC

from solicitudes_partner.modulos.solicitudes.aplicacion.vistas import (
    ActualizacionVista,
    VistaSolicitud,
)
from solicitudes_partner.modulos.solicitudes.dominio.entidades import SolicitudPartner
from solicitudes_partner.modulos.solicitudes.dominio.eventos import (
    SolicitudPartnerListaParaAtencion,
    SolicitudPartnerRechazada,
    SolicitudPartnerRegistrada,
)
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
    Admisibilidad,
    EstadoSolicitud,
    MotivoRechazo,
    TipoRedProveedores,
    TipoSolicitud,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.orm import SolicitudSQL
from solicitudes_partner.modulos.solicitudes.infraestructura.serializacion import (
    cargar_datos,
    cargar_resultado,
    guardar_datos,
    guardar_resultado,
)
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio
from solicitudes_partner.seedwork.infraestructura.serializacion import (
    Documento,
    entero,
    identidad,
    instante,
    texto,
)


def valores(solicitud: SolicitudPartner) -> Documento:
    solicitud.__post_init__()
    return dict(
        id=solicitud.id,
        id_partner=solicitud.datos.id_partner,
        referencia_externa=solicitud.datos.referencia_externa,
        datos=guardar_datos(solicitud.datos),
        creada_en=solicitud.creada_en,
        actualizada_en=solicitud.actualizada_en,
        estado=solicitud.estado.value,
        version=solicitud.version,
        evaluacion=guardar_resultado(solicitud.evaluacion) if solicitud.evaluacion else None,
    )


def reconstruir(fila: SolicitudSQL) -> SolicitudPartner:
    return SolicitudPartner.reconstruir(
        id=fila.id,
        datos=cargar_datos(fila.datos),
        creada_en=fila.creada_en,
        actualizada_en=fila.actualizada_en,
        estado=EstadoSolicitud(fila.estado),
        version=fila.version,
        evaluacion=cargar_resultado(fila.evaluacion) if fila.evaluacion is not None else None,
    )


def guardar_vista(vista: VistaSolicitud) -> Documento:
    documento = asdict(vista)
    documento.update(
        id_solicitud=str(vista.id_solicitud),
        id_partner=str(vista.id_partner),
        id_politica=str(vista.id_politica) if vista.id_politica else None,
        creada_en=vista.creada_en.astimezone(UTC).isoformat(),
        actualizada_en=vista.actualizada_en.astimezone(UTC).isoformat(),
    )
    return documento


def cargar_vista(documento: Documento) -> VistaSolicitud:
    return VistaSolicitud(
        id_solicitud=identidad(documento, "id_solicitud"),
        id_partner=identidad(documento, "id_partner"),
        referencia_externa=texto(documento, "referencia_externa"),
        categoria=texto(documento, "categoria"),
        tipo_solicitud=TipoSolicitud(texto(documento, "tipo_solicitud")),
        estado=EstadoSolicitud(texto(documento, "estado")),
        version_solicitud=entero(documento, "version_solicitud"),
        creada_en=instante(documento, "creada_en"),
        actualizada_en=instante(documento, "actualizada_en"),
        resultado=Admisibilidad(texto(documento, "resultado"))
        if documento["resultado"] is not None
        else None,
        motivo=MotivoRechazo(texto(documento, "motivo"))
        if documento["motivo"] is not None
        else None,
        tipo_red=TipoRedProveedores(texto(documento, "tipo_red"))
        if documento["tipo_red"] is not None
        else None,
        id_politica=identidad(documento, "id_politica")
        if documento["id_politica"] is not None
        else None,
        version_politica=entero(documento, "version_politica")
        if documento["version_politica"] is not None
        else None,
    )


def actualizacion_desde_evento(evento: EventoDominio) -> ActualizacionVista:
    if not isinstance(
        evento,
        (SolicitudPartnerRegistrada, SolicitudPartnerListaParaAtencion, SolicitudPartnerRechazada),
    ):
        raise ValueError("Evento no proyectable")
    if isinstance(evento, SolicitudPartnerRegistrada):
        evaluacion = None
        estado = EstadoSolicitud.RECIBIDA
        creada_en = evento.instante
    else:
        evaluacion = evento.evaluacion
        estado = evento.estado
        creada_en = evento.creada_en
    return ActualizacionVista(
        evento.id_evento,
        VistaSolicitud(
            id_solicitud=evento.id_solicitud,
            id_partner=evento.datos.id_partner,
            referencia_externa=evento.datos.referencia_externa,
            categoria=evento.datos.categoria,
            tipo_solicitud=evento.datos.tipo,
            estado=estado,
            version_solicitud=evento.version_solicitud,
            creada_en=creada_en,
            actualizada_en=evento.instante,
            resultado=evaluacion.resultado if evaluacion else None,
            motivo=evaluacion.motivo if evaluacion else None,
            tipo_red=evaluacion.tipo_red if evaluacion else None,
            id_politica=evaluacion.id_politica if evaluacion else None,
            version_politica=evaluacion.version_politica if evaluacion else None,
        ),
    )
