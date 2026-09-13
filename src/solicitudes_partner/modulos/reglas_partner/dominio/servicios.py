from datetime import datetime
from uuid import UUID

from solicitudes_partner.modulos.reglas_partner.dominio.entidades import EvaluacionReglasPartner
from solicitudes_partner.modulos.reglas_partner.dominio.eventos import ReglasDePartnerEvaluadas
from solicitudes_partner.modulos.reglas_partner.dominio.excepciones import (
    ErrorConfiguracionPolitica,
)
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import (
    MotivoRechazo,
    PoliticaPartner,
    ResultadoEvaluacion,
)
from solicitudes_partner.modulos.solicitudes.dominio.eventos import (
    SolicitudPartnerRegistrada,
)
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
    TipoSolicitud,
)
from solicitudes_partner.seedwork.dominio.validaciones import validar_instante


def evaluar_solicitud(
    registro: SolicitudPartnerRegistrada,
    politica: PoliticaPartner | None,
    *,
    id_evaluacion: UUID,
    id_evento: UUID,
    instante: datetime,
) -> EvaluacionReglasPartner:
    if not isinstance(politica, PoliticaPartner):
        raise ErrorConfiguracionPolitica("No existe una politica valida para el partner")
    politica.__post_init__()
    if politica.id_partner != registro.datos.id_partner:
        raise ErrorConfiguracionPolitica("La politica pertenece a otro partner")
    validar_instante(instante)
    if instante < registro.instante:
        raise ValueError("La evaluacion no puede preceder al registro")
    sin_aprobacion = (
        registro.datos.tipo is TipoSolicitud.SINIESTRO and registro.datos.aprobacion_previa is False
    )
    evento = ReglasDePartnerEvaluadas(
        id_evento=id_evento,
        instante=instante,
        id_evaluacion=id_evaluacion,
        id_solicitud=registro.id_solicitud,
        id_partner=registro.datos.id_partner,
        version_solicitud=registro.version_solicitud,
        id_politica=politica.id,
        version_politica=politica.version,
        resultado=ResultadoEvaluacion.NO_ADMISIBLE
        if sin_aprobacion
        else ResultadoEvaluacion.ADMISIBLE,
        tipo_red=None if sin_aprobacion else politica.tipo_red,
        motivo=MotivoRechazo.APROBACION_PREVIA_REQUERIDA if sin_aprobacion else None,
    )
    return EvaluacionReglasPartner(id=id_evaluacion, evento=evento)
