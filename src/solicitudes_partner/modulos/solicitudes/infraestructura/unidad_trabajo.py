from solicitudes_partner.modulos.solicitudes.infraestructura.repositorios import (
    RepositorioSolicitudesSQL,
)
from solicitudes_partner.seedwork.infraestructura.unidad_trabajo_sqlalchemy import UnidadTrabajoSQL


class UnidadTrabajoSolicitudesSQL(UnidadTrabajoSQL):
    restricciones_reintentables = frozenset({"uq_solicitud_referencia"})
    solicitudes: RepositorioSolicitudesSQL

    def _crear_repositorios(self) -> None:
        self.solicitudes = RepositorioSolicitudesSQL(self.sesion)
