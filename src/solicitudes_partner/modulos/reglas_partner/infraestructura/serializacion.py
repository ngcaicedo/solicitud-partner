from datetime import UTC

from solicitudes_partner.modulos.reglas_partner.dominio.eventos import ReglasDePartnerEvaluadas
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import (
    MotivoRechazo,
    ResultadoEvaluacion,
    TipoRedProveedores,
)
from solicitudes_partner.seedwork.infraestructura.serializacion import (
    Documento,
    entero,
    identidad,
    instante,
    texto,
)


def serializar(evento: ReglasDePartnerEvaluadas) -> Documento:
    evento.__post_init__()
    return dict(
        tipo="ReglasDePartnerEvaluadas",
        version_formato=1,
        id_evento=str(evento.id_evento),
        instante=evento.instante.astimezone(UTC).isoformat(),
        id_evaluacion=str(evento.id_evaluacion),
        id_solicitud=str(evento.id_solicitud),
        id_partner=str(evento.id_partner),
        version_solicitud=evento.version_solicitud,
        id_politica=str(evento.id_politica),
        version_politica=evento.version_politica,
        resultado=evento.resultado.value,
        tipo_red=evento.tipo_red.value if evento.tipo_red else None,
        motivo=evento.motivo.value if evento.motivo else None,
    )


def decodificar(documento: Documento) -> ReglasDePartnerEvaluadas:
    if (
        entero(documento, "version_formato") != 1
        or texto(documento, "tipo") != "ReglasDePartnerEvaluadas"
    ):
        raise ValueError("Formato de evaluacion desconocido")
    return ReglasDePartnerEvaluadas(
        id_evento=identidad(documento, "id_evento"),
        instante=instante(documento, "instante"),
        id_evaluacion=identidad(documento, "id_evaluacion"),
        id_solicitud=identidad(documento, "id_solicitud"),
        id_partner=identidad(documento, "id_partner"),
        version_solicitud=entero(documento, "version_solicitud"),
        id_politica=identidad(documento, "id_politica"),
        version_politica=entero(documento, "version_politica"),
        resultado=ResultadoEvaluacion(texto(documento, "resultado")),
        tipo_red=TipoRedProveedores(texto(documento, "tipo_red"))
        if documento["tipo_red"] is not None
        else None,
        motivo=MotivoRechazo(texto(documento, "motivo"))
        if documento["motivo"] is not None
        else None,
    )
