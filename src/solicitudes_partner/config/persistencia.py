from solicitudes_partner.config.database import Database
from solicitudes_partner.config.serializacion import serializar_evento
from solicitudes_partner.modulos.reglas_partner.infraestructura.unidad_trabajo import (
    UnidadTrabajoReglasSQL,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.unidad_trabajo import (
    UnidadTrabajoSolicitudesSQL,
)
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio
from solicitudes_partner.seedwork.infraestructura.orm import BaseSQL

metadata = BaseSQL.metadata


def destinos_laboratorio(evento: EventoDominio) -> tuple[str, ...]:
    return (f"laboratorio.{type(evento).__name__}",)


def crear_uow_solicitudes(base: Database) -> UnidadTrabajoSolicitudesSQL:
    return UnidadTrabajoSolicitudesSQL(
        base.session_factory, serializar_evento, destinos_laboratorio
    )


def crear_uow_reglas(base: Database) -> UnidadTrabajoReglasSQL:
    return UnidadTrabajoReglasSQL(base.session_factory, serializar_evento, destinos_laboratorio)
