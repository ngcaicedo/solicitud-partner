from typing import Protocol
from uuid import UUID

from solicitudes_partner.modulos.reglas_partner.dominio.entidades import EvaluacionReglasPartner
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import PoliticaPartner
from solicitudes_partner.modulos.solicitudes.dominio.eventos import (
    SolicitudPartnerRegistrada,
)
from solicitudes_partner.seedwork.dominio.repositorios import Repositorio


class RepositorioEvaluaciones(Repositorio[EvaluacionReglasPartner], Protocol):
    def obtener_por_solicitud(self, id_solicitud: UUID) -> EvaluacionReglasPartner | None: ...

    def obtener_origen(self, id_solicitud: UUID) -> SolicitudPartnerRegistrada | None: ...

    def guardar_origen(self, registro: SolicitudPartnerRegistrada) -> None: ...


class RepositorioPoliticas(Protocol):
    def obtener(self, id_partner: UUID) -> PoliticaPartner | None: ...
