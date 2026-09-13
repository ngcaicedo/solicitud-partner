from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from solicitudes_partner.seedwork.dominio.objetos_valor import ObjetoValor
from solicitudes_partner.seedwork.dominio.validaciones import (
    validar_identidad,
    validar_instante,
    validar_texto,
    validar_version,
)


class TipoSolicitud(StrEnum):
    SINIESTRO = "SINIESTRO"
    INSTALACION = "INSTALACION"


class EstadoSolicitud(StrEnum):
    RECIBIDA = "RECIBIDA"
    LISTA_PARA_ATENCION = "LISTA_PARA_ATENCION"
    RECHAZADA = "RECHAZADA"


@dataclass(frozen=True, kw_only=True)
class DatosSolicitud(ObjetoValor):
    id_partner: UUID
    referencia_externa: str
    categoria: str
    tipo: TipoSolicitud
    aprobacion_previa: bool | None = None

    def __post_init__(self) -> None:
        validar_identidad(self.id_partner)
        validar_texto(self.referencia_externa)
        validar_texto(self.categoria)
        if not isinstance(self.tipo, TipoSolicitud):
            raise ValueError("Tipo de solicitud invalido")
        if self.aprobacion_previa is not None and type(self.aprobacion_previa) is not bool:
            raise ValueError("La aprobacion previa debe ser booleana")
        if self.tipo is TipoSolicitud.SINIESTRO and self.aprobacion_previa is None:
            raise ValueError("El siniestro requiere declarar aprobacion previa")


class Admisibilidad(StrEnum):
    ADMISIBLE = "ADMISIBLE"
    NO_ADMISIBLE = "NO_ADMISIBLE"


class TipoRedProveedores(StrEnum):
    GENERAL_HDA = "GENERAL_HDA"
    HOMOLOGADA_PARTNER = "HOMOLOGADA_PARTNER"


class MotivoRechazo(StrEnum):
    APROBACION_PREVIA_REQUERIDA = "APROBACION_PREVIA_REQUERIDA"


@dataclass(frozen=True, kw_only=True)
class ResultadoEvaluacion(ObjetoValor):
    id_evento: UUID
    instante: datetime
    id_evaluacion: UUID
    id_solicitud: UUID
    id_partner: UUID
    version_solicitud: int
    id_politica: UUID
    version_politica: int
    resultado: Admisibilidad
    tipo_red: TipoRedProveedores | None = None
    motivo: MotivoRechazo | None = None

    def __post_init__(self) -> None:
        for identidad in (
            self.id_evento,
            self.id_evaluacion,
            self.id_solicitud,
            self.id_partner,
            self.id_politica,
        ):
            validar_identidad(identidad)
        validar_instante(self.instante)
        validar_version(self.version_solicitud)
        validar_version(self.version_politica)
        if self.resultado is Admisibilidad.ADMISIBLE:
            if not isinstance(self.tipo_red, TipoRedProveedores) or self.motivo is not None:
                raise ValueError("Un resultado admisible requiere red y ningun motivo de rechazo")
        elif self.resultado is Admisibilidad.NO_ADMISIBLE:
            if self.tipo_red is not None or not isinstance(self.motivo, MotivoRechazo):
                raise ValueError("Un resultado no admisible requiere motivo y ninguna red")
        else:
            raise ValueError("Admisibilidad invalida")
