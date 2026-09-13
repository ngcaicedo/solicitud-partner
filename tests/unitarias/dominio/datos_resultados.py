from datetime import timedelta
from uuid import UUID

from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
    Admisibilidad,
    MotivoRechazo,
    ResultadoEvaluacion,
    TipoRedProveedores,
)

from .datos import ID_EVALUACION, ID_PARTNER, ID_POLITICA, ID_SOLICITUD, INSTANTE


def resultado_solicitud(aprobacion: bool = True) -> ResultadoEvaluacion:
    return ResultadoEvaluacion(
        id_evento=UUID(int=11),
        instante=INSTANTE + timedelta(seconds=1),
        id_evaluacion=ID_EVALUACION,
        id_solicitud=ID_SOLICITUD,
        id_partner=ID_PARTNER,
        version_solicitud=1,
        id_politica=ID_POLITICA,
        version_politica=1,
        resultado=Admisibilidad.ADMISIBLE if aprobacion else Admisibilidad.NO_ADMISIBLE,
        tipo_red=TipoRedProveedores.GENERAL_HDA if aprobacion else None,
        motivo=None if aprobacion else MotivoRechazo.APROBACION_PREVIA_REQUERIDA,
    )
