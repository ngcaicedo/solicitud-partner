from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from solicitudes_partner.modulos.reglas_partner.dominio.excepciones import (
    ErrorConfiguracionPolitica,
)
from solicitudes_partner.seedwork.dominio.objetos_valor import ObjetoValor
from solicitudes_partner.seedwork.dominio.validaciones import validar_identidad, validar_version


class TipoRedProveedores(StrEnum):
    GENERAL_HDA = "GENERAL_HDA"
    HOMOLOGADA_PARTNER = "HOMOLOGADA_PARTNER"


class ResultadoEvaluacion(StrEnum):
    ADMISIBLE = "ADMISIBLE"
    NO_ADMISIBLE = "NO_ADMISIBLE"


class MotivoRechazo(StrEnum):
    APROBACION_PREVIA_REQUERIDA = "APROBACION_PREVIA_REQUERIDA"


@dataclass(frozen=True, kw_only=True)
class PoliticaPartner(ObjetoValor):
    id: UUID
    id_partner: UUID
    version: int
    tipo_red: TipoRedProveedores

    def __post_init__(self) -> None:
        try:
            validar_identidad(self.id)
            validar_identidad(self.id_partner)
            validar_version(self.version)
            if not isinstance(self.tipo_red, TipoRedProveedores):
                raise ValueError("Tipo de red invalido")
        except ValueError as error:
            raise ErrorConfiguracionPolitica(str(error)) from error
