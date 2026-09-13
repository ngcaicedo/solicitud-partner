from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
    Admisibilidad,
    DatosSolicitud,
    EstadoSolicitud,
    ResultadoEvaluacion,
)
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
    TipoSolicitud as TipoSolicitud,
)
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio
from solicitudes_partner.seedwork.dominio.validaciones import (
    validar_identidad,
    validar_instante,
    validar_version,
)


@dataclass(frozen=True, kw_only=True)
class SolicitudPartnerRegistrada(EventoDominio):
    id_solicitud: UUID
    datos: DatosSolicitud
    version_solicitud: int = 1

    def __post_init__(self) -> None:
        super().__post_init__()
        validar_identidad(self.id_solicitud)
        validar_version(self.version_solicitud)
        if self.version_solicitud != 1 or not isinstance(self.datos, DatosSolicitud):
            raise ValueError("El registro requiere datos validos y version 1")


def validar_evaluacion_solicitud(
    evaluacion: ResultadoEvaluacion,
    id_solicitud: UUID,
    datos: DatosSolicitud,
    creada_en: datetime,
    actualizada_en: datetime,
) -> None:
    if not isinstance(evaluacion, ResultadoEvaluacion):
        raise ValueError("Contrato de evaluacion invalido")
    evaluacion.__post_init__()
    if evaluacion.id_solicitud != id_solicitud or evaluacion.id_partner != datos.id_partner:
        raise ValueError("La evaluacion pertenece a otra solicitud o partner")
    if evaluacion.version_solicitud != 1:
        raise ValueError("La evaluacion debe corresponder a la version inicial")
    if not creada_en <= evaluacion.instante <= actualizada_en:
        raise ValueError("La evaluacion debe ocurrir entre el registro y la transicion")


@dataclass(frozen=True, kw_only=True)
class _SolicitudPartnerFinalizada(EventoDominio):
    id_solicitud: UUID
    datos: DatosSolicitud
    creada_en: datetime
    evaluacion: ResultadoEvaluacion
    version_solicitud: int = 2

    def __post_init__(self) -> None:
        super().__post_init__()
        validar_identidad(self.id_solicitud)
        validar_instante(self.creada_en)
        validar_version(self.version_solicitud)
        if self.version_solicitud != 2 or not isinstance(self.datos, DatosSolicitud):
            raise ValueError("El evento final requiere datos validos y version 2")
        validar_evaluacion_solicitud(
            self.evaluacion, self.id_solicitud, self.datos, self.creada_en, self.instante
        )


@dataclass(frozen=True, kw_only=True)
class SolicitudPartnerListaParaAtencion(_SolicitudPartnerFinalizada):
    def __post_init__(self) -> None:
        super().__post_init__()
        if self.evaluacion.resultado is not Admisibilidad.ADMISIBLE:
            raise ValueError("Una solicitud lista requiere evaluacion admisible")

    @property
    def estado(self) -> EstadoSolicitud:
        return EstadoSolicitud.LISTA_PARA_ATENCION


@dataclass(frozen=True, kw_only=True)
class SolicitudPartnerRechazada(_SolicitudPartnerFinalizada):
    def __post_init__(self) -> None:
        super().__post_init__()
        if self.evaluacion.resultado is not Admisibilidad.NO_ADMISIBLE:
            raise ValueError("Una solicitud rechazada requiere evaluacion no admisible")

    @property
    def estado(self) -> EstadoSolicitud:
        return EstadoSolicitud.RECHAZADA
