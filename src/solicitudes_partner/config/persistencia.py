from solicitudes_partner.config.database import Database
from solicitudes_partner.config.rutas import DESTINOS_ADMITIDOS, destinos_evento
from solicitudes_partner.config.serializacion import serializar_evento
from solicitudes_partner.modulos.reglas_partner.infraestructura.unidad_trabajo import (
    UnidadTrabajoReglasSQL,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.unidad_trabajo import (
    UnidadTrabajoSolicitudesSQL,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.vistas import VistaSolicitudSQL
from solicitudes_partner.seedwork.infraestructura.outbox import RepositorioOutbox

metadata = VistaSolicitudSQL.metadata


def crear_uow_solicitudes(base: Database) -> UnidadTrabajoSolicitudesSQL:
    return UnidadTrabajoSolicitudesSQL(base.session_factory, serializar_evento, destinos_evento)


def crear_uow_reglas(base: Database) -> UnidadTrabajoReglasSQL:
    return UnidadTrabajoReglasSQL(base.session_factory, serializar_evento, destinos_evento)


def verificar_destinos(base: Database) -> None:
    outbox = RepositorioOutbox(base.session_factory)
    if outbox.hay_pendientes_fuera_de(DESTINOS_ADMITIDOS):
        raise ValueError(
            "Hay destinos pendientes desconocidos; inspeccionar outbox antes de iniciar"
        )
