from solicitudes_partner.modulos.reglas_partner.infraestructura.repositorios import (
    RepositorioEvaluacionesSQL,
    RepositorioPoliticasSQL,
)
from solicitudes_partner.seedwork.infraestructura.unidad_trabajo_sqlalchemy import UnidadTrabajoSQL


class UnidadTrabajoReglasSQL(UnidadTrabajoSQL):
    restricciones_reintentables = frozenset({"uq_evaluacion_solicitud"})
    evaluaciones: RepositorioEvaluacionesSQL
    politicas: RepositorioPoliticasSQL

    def _crear_repositorios(self) -> None:
        self.evaluaciones = RepositorioEvaluacionesSQL(self.sesion)
        self.politicas = RepositorioPoliticasSQL(self.sesion)
