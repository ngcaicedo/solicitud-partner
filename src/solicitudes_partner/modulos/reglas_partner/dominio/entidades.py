from dataclasses import dataclass

from solicitudes_partner.modulos.reglas_partner.contratos import ReglasDePartnerEvaluadas
from solicitudes_partner.seedwork.dominio.entidades import Entidad


@dataclass(frozen=True, eq=False, kw_only=True)
class EvaluacionReglasPartner(Entidad):
    evento: ReglasDePartnerEvaluadas

    def __post_init__(self) -> None:
        super().__post_init__()
        if (
            not isinstance(self.evento, ReglasDePartnerEvaluadas)
            or self.id != self.evento.id_evaluacion
        ):
            raise ValueError("La identidad de evaluacion debe coincidir con su contrato")
