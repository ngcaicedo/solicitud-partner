from datetime import UTC

from solicitudes_partner.modulos.solicitudes.dominio.eventos import (
    SolicitudPartnerListaParaAtencion,
    SolicitudPartnerRechazada,
    SolicitudPartnerRegistrada,
)
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
    Admisibilidad,
    DatosSolicitud,
    MotivoRechazo,
    ResultadoEvaluacion,
    TipoRedProveedores,
    TipoSolicitud,
)
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio
from solicitudes_partner.seedwork.infraestructura.serializacion import (
    Documento,
    entero,
    identidad,
    instante,
    objeto,
    texto,
)


def guardar_datos(datos: DatosSolicitud) -> Documento:
    datos.__post_init__()
    return dict(
        id_partner=str(datos.id_partner),
        referencia_externa=datos.referencia_externa,
        categoria=datos.categoria,
        tipo=datos.tipo.value,
        aprobacion_previa=datos.aprobacion_previa,
    )


def cargar_datos(documento: Documento) -> DatosSolicitud:
    return DatosSolicitud(
        id_partner=identidad(documento, "id_partner"),
        referencia_externa=texto(documento, "referencia_externa"),
        categoria=texto(documento, "categoria"),
        tipo=TipoSolicitud(texto(documento, "tipo")),
        aprobacion_previa=documento["aprobacion_previa"],
    )


def guardar_resultado(resultado: ResultadoEvaluacion) -> Documento:
    resultado.__post_init__()
    return dict(
        id_evento=str(resultado.id_evento),
        instante=resultado.instante.astimezone(UTC).isoformat(),
        id_evaluacion=str(resultado.id_evaluacion),
        id_solicitud=str(resultado.id_solicitud),
        id_partner=str(resultado.id_partner),
        version_solicitud=resultado.version_solicitud,
        id_politica=str(resultado.id_politica),
        version_politica=resultado.version_politica,
        resultado=resultado.resultado.value,
        tipo_red=resultado.tipo_red.value if resultado.tipo_red else None,
        motivo=resultado.motivo.value if resultado.motivo else None,
    )


def cargar_resultado(documento: Documento) -> ResultadoEvaluacion:
    return ResultadoEvaluacion(
        id_evento=identidad(documento, "id_evento"),
        instante=instante(documento, "instante"),
        id_evaluacion=identidad(documento, "id_evaluacion"),
        id_solicitud=identidad(documento, "id_solicitud"),
        id_partner=identidad(documento, "id_partner"),
        version_solicitud=entero(documento, "version_solicitud"),
        id_politica=identidad(documento, "id_politica"),
        version_politica=entero(documento, "version_politica"),
        resultado=Admisibilidad(texto(documento, "resultado")),
        tipo_red=TipoRedProveedores(texto(documento, "tipo_red"))
        if documento["tipo_red"] is not None
        else None,
        motivo=MotivoRechazo(texto(documento, "motivo"))
        if documento["motivo"] is not None
        else None,
    )


def serializar(evento: EventoDominio) -> Documento:
    if not isinstance(
        evento,
        (SolicitudPartnerRegistrada, SolicitudPartnerListaParaAtencion, SolicitudPartnerRechazada),
    ):
        raise ValueError("Evento ajeno a Solicitudes")
    evento.__post_init__()
    documento = dict(
        tipo=type(evento).__name__,
        version_formato=1,
        id_evento=str(evento.id_evento),
        instante=evento.instante.astimezone(UTC).isoformat(),
        id_solicitud=str(evento.id_solicitud),
        version_solicitud=evento.version_solicitud,
        datos=guardar_datos(evento.datos),
    )
    if not isinstance(evento, SolicitudPartnerRegistrada):
        documento.update(
            creada_en=evento.creada_en.astimezone(UTC).isoformat(),
            evaluacion=guardar_resultado(evento.evaluacion),
        )
    return documento


def decodificar(documento: Documento) -> EventoDominio:
    if entero(documento, "version_formato") != 1:
        raise ValueError("Version de formato desconocida")
    comunes: Documento = dict(
        id_evento=identidad(documento, "id_evento"),
        instante=instante(documento, "instante"),
        id_solicitud=identidad(documento, "id_solicitud"),
        version_solicitud=entero(documento, "version_solicitud"),
        datos=cargar_datos(objeto(documento, "datos")),
    )
    tipo = texto(documento, "tipo")
    if tipo == "SolicitudPartnerRegistrada":
        return SolicitudPartnerRegistrada(**comunes)
    if tipo not in {"SolicitudPartnerListaParaAtencion", "SolicitudPartnerRechazada"}:
        raise ValueError("Tipo de evento desconocido")
    clase = (
        SolicitudPartnerListaParaAtencion
        if tipo == "SolicitudPartnerListaParaAtencion"
        else SolicitudPartnerRechazada
    )
    return clase(
        **comunes,
        creada_en=instante(documento, "creada_en"),
        evaluacion=cargar_resultado(objeto(documento, "evaluacion")),
    )
