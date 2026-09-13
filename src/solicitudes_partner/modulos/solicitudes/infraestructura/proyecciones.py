import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.orm import Session

from solicitudes_partner.modulos.solicitudes.aplicacion.vistas import ActualizacionVista
from solicitudes_partner.modulos.solicitudes.infraestructura.mapeadores import guardar_vista
from solicitudes_partner.modulos.solicitudes.infraestructura.repositorios import (
    RepositorioProyeccionSQL,
)
from solicitudes_partner.seedwork.infraestructura.inbox import preparar


class ProyectorSolicitudes:
    consumidor: ClassVar[str] = "solicitudes.proyeccion.v1"

    def __init__(self, crear_sesion: Callable[[], Session]) -> None:
        self.crear_sesion = crear_sesion

    def proyectar(self, actualizacion: ActualizacionVista) -> bool:
        actualizacion.__post_init__()
        with self.crear_sesion() as sesion:
            if not preparar(
                sesion, self.consumidor, actualizacion.id_evento, guardar_vista(actualizacion.vista)
            ):
                return False
            aplicada = RepositorioProyeccionSQL(sesion).actualizar(actualizacion.vista)
            sesion.commit()
        if aplicada:
            demora = (datetime.now(UTC) - actualizacion.vista.actualizada_en).total_seconds()
            logging.getLogger(__name__).info(
                "Proyeccion confirmada id=%s version=%s latencia_segundos=%.6f",
                actualizacion.vista.id_solicitud,
                actualizacion.vista.version_solicitud,
                demora,
            )
        return aplicada
