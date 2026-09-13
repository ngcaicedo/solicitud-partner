from dataclasses import dataclass
from uuid import UUID

from solicitudes_partner.modulos.solicitudes.aplicacion.consultas import RepositorioLectura
from solicitudes_partner.modulos.solicitudes.aplicacion.vistas import VistaSolicitud


@dataclass(frozen=True)
class ConsultarSolicitudHandler:
    repositorio: RepositorioLectura

    def __call__(self, id_partner: UUID, id_solicitud: UUID) -> VistaSolicitud | None:
        return self.repositorio.obtener(id_partner, id_solicitud)


@dataclass(frozen=True)
class ListarSolicitudesHandler:
    repositorio: RepositorioLectura

    def __call__(
        self, id_partner: UUID, limite: int = 20, desplazamiento: int = 0
    ) -> list[VistaSolicitud]:
        if not 1 <= limite <= 100 or desplazamiento < 0:
            raise ValueError("Paginacion invalida")
        return self.repositorio.listar(id_partner, limite, desplazamiento)
