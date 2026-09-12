from dataclasses import dataclass
from uuid import UUID

from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import (
    MotivoRechazo as MotivoRechazo,
)
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import (
    ResultadoEvaluacion as ResultadoEvaluacion,
)
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import (
    TipoRedProveedores as TipoRedProveedores,
)
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio
from solicitudes_partner.seedwork.dominio.validaciones import validar_identidad, validar_version


@dataclass(frozen=True, kw_only=True)
class ReglasDePartnerEvaluadas(EventoDominio):
    id_evaluacion: UUID
    id_solicitud: UUID
    id_partner: UUID
    version_solicitud: int
    id_politica: UUID
    version_politica: int
    resultado: ResultadoEvaluacion
    tipo_red: TipoRedProveedores | None = None
    motivo: MotivoRechazo | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        for identidad in (self.id_evaluacion, self.id_solicitud, self.id_partner, self.id_politica):
            validar_identidad(identidad)
        validar_version(self.version_solicitud)
        validar_version(self.version_politica)
        if self.resultado is ResultadoEvaluacion.ADMISIBLE:
            if not isinstance(self.tipo_red, TipoRedProveedores) or self.motivo is not None:
                raise ValueError("Una evaluacion admisible requiere red y ningun motivo de rechazo")
        elif self.resultado is ResultadoEvaluacion.NO_ADMISIBLE:
            if self.tipo_red is not None or not isinstance(self.motivo, MotivoRechazo):
                raise ValueError("Una evaluacion no admisible requiere motivo y ninguna red")
        else:
            raise ValueError("Resultado de evaluacion invalido")
