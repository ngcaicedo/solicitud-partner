from typing import Protocol
from uuid import UUID

from solicitudes_partner.seedwork.dominio.entidades import Entidad


class Repositorio[Modelo: Entidad](Protocol):
    def obtener(self, id: UUID) -> Modelo | None: ...

    def guardar(self, modelo: Modelo) -> None: ...
