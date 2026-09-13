from datetime import UTC, datetime, timedelta
from uuid import UUID

from solicitudes_partner.modulos.reglas_partner.dominio.eventos import (
    ReglasDePartnerEvaluadas,
)
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import (
    PoliticaPartner,
    TipoRedProveedores,
)
from solicitudes_partner.modulos.reglas_partner.dominio.servicios import evaluar_solicitud
from solicitudes_partner.modulos.solicitudes.dominio.entidades import SolicitudPartner
from solicitudes_partner.modulos.solicitudes.dominio.eventos import (
    SolicitudPartnerRegistrada,
)
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
    DatosSolicitud,
    TipoSolicitud,
)

INSTANTE = datetime(2026, 9, 12, 15, tzinfo=UTC)
ID_SOLICITUD = UUID(int=1)
ID_PARTNER = UUID(int=2)
ID_POLITICA = UUID(int=3)
ID_EVALUACION = UUID(int=4)


def datos_solicitud(
    aprobacion_previa: bool | None = True,
    tipo: TipoSolicitud = TipoSolicitud.SINIESTRO,
) -> DatosSolicitud:
    return DatosSolicitud(
        id_partner=ID_PARTNER,
        referencia_externa="SIN-100",
        categoria="plomeria",
        tipo=tipo,
        aprobacion_previa=aprobacion_previa,
    )


def solicitud_nueva(
    aprobacion_previa: bool | None = True,
    tipo: TipoSolicitud = TipoSolicitud.SINIESTRO,
) -> SolicitudPartner:
    return SolicitudPartner.registrar(
        id=ID_SOLICITUD,
        datos=datos_solicitud(aprobacion_previa, tipo),
        id_evento=UUID(int=10),
        instante=INSTANTE,
    )


def registro(
    aprobacion_previa: bool | None = True,
    tipo: TipoSolicitud = TipoSolicitud.SINIESTRO,
) -> SolicitudPartnerRegistrada:
    return SolicitudPartnerRegistrada(
        id_evento=UUID(int=10),
        instante=INSTANTE,
        id_solicitud=ID_SOLICITUD,
        datos=datos_solicitud(aprobacion_previa, tipo),
        version_solicitud=1,
    )


def politica(
    red: TipoRedProveedores = TipoRedProveedores.GENERAL_HDA,
) -> PoliticaPartner:
    return PoliticaPartner(id=ID_POLITICA, id_partner=ID_PARTNER, version=1, tipo_red=red)


def resultado(
    aprobacion_previa: bool = True,
    red: TipoRedProveedores = TipoRedProveedores.GENERAL_HDA,
) -> ReglasDePartnerEvaluadas:
    return evaluar_solicitud(
        registro(aprobacion_previa),
        politica(red),
        id_evaluacion=ID_EVALUACION,
        id_evento=UUID(int=11),
        instante=INSTANTE + timedelta(seconds=1),
    ).evento
