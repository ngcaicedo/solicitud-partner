from typing import Protocol
from uuid import UUID

from solicitudes_partner.modulos.reglas_partner.dominio.entidades import EvaluacionReglasPartner
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import PoliticaPartner
from solicitudes_partner.seedwork.dominio.repositorios import Repositorio


class RepositorioEvaluaciones(Repositorio[EvaluacionReglasPartner], Protocol):
    pass


class RepositorioPoliticas(Protocol):
    def obtener(self, id_partner: UUID) -> PoliticaPartner | None: ...
