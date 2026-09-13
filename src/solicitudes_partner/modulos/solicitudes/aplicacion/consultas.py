from typing import Protocol
from uuid import UUID

from solicitudes_partner.modulos.solicitudes.aplicacion.vistas import VistaSolicitud


class RepositorioLectura(Protocol):
    def obtener(self, id_partner: UUID, id_solicitud: UUID) -> VistaSolicitud | None: ...

    def listar(
        self, id_partner: UUID, limite: int, desplazamiento: int
    ) -> list[VistaSolicitud]: ...
