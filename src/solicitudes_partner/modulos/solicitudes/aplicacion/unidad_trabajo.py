from typing import Protocol

from solicitudes_partner.modulos.solicitudes.dominio.repositorios import RepositorioSolicitudes
from solicitudes_partner.seedwork.aplicacion.unidad_trabajo import UnidadTrabajo


class UnidadTrabajoSolicitudes(UnidadTrabajo, Protocol):
    @property
    def solicitudes(self) -> RepositorioSolicitudes: ...
