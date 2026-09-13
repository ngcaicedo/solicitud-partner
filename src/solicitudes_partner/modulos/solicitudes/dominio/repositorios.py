from typing import Protocol
from uuid import UUID

from solicitudes_partner.modulos.solicitudes.dominio.entidades import SolicitudPartner
from solicitudes_partner.seedwork.dominio.repositorios import Repositorio


class RepositorioSolicitudes(Repositorio[SolicitudPartner], Protocol):
    def obtener_por_referencia(
        self, id_partner: UUID, referencia: str
    ) -> SolicitudPartner | None: ...
