from typing import Protocol

from solicitudes_partner.modulos.reglas_partner.dominio.repositorios import (
    RepositorioEvaluaciones,
    RepositorioPoliticas,
)
from solicitudes_partner.seedwork.aplicacion.unidad_trabajo import UnidadTrabajo


class UnidadTrabajoReglas(UnidadTrabajo, Protocol):
    @property
    def evaluaciones(self) -> RepositorioEvaluaciones: ...

    @property
    def politicas(self) -> RepositorioPoliticas: ...
