from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from solicitudes_partner.config.database import Database

from solicitudes_partner.modulos.reglas_partner.aplicacion.handlers.evaluar_registro import (
    EvaluarRegistroHandler,
)
from solicitudes_partner.modulos.reglas_partner.aplicacion.unidad_trabajo import UnidadTrabajoReglas
from solicitudes_partner.modulos.reglas_partner.dominio.eventos import (
    ReglasDePartnerEvaluadas,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.handlers.aplicar_resultado import (
    AplicarResultadoEvaluacionHandler,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.handlers.registrar_solicitud import (
    RegistrarSolicitudHandler,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.unidad_trabajo import (
    UnidadTrabajoSolicitudes,
)
from solicitudes_partner.modulos.solicitudes.dominio.eventos import (
    SolicitudPartnerRegistrada,
)
from solicitudes_partner.seedwork.aplicacion.bus_eventos import BusEventos
from solicitudes_partner.seedwork.aplicacion.identificadores import GeneradorIdentificadores
from solicitudes_partner.seedwork.aplicacion.reloj import Reloj


@dataclass(frozen=True)
class FlujoInterno:
    registrar: RegistrarSolicitudHandler
    evaluar: EvaluarRegistroHandler
    aplicar: AplicarResultadoEvaluacionHandler


def componer_flujo(
    crear_solicitudes: Callable[[], UnidadTrabajoSolicitudes],
    crear_reglas: Callable[[], UnidadTrabajoReglas],
    reloj: Reloj,
    identificadores: GeneradorIdentificadores,
    bus: BusEventos,
) -> FlujoInterno:
    flujo = FlujoInterno(
        RegistrarSolicitudHandler(crear_solicitudes, reloj, identificadores),
        EvaluarRegistroHandler(crear_reglas, reloj, identificadores),
        AplicarResultadoEvaluacionHandler(crear_solicitudes, reloj, identificadores),
    )
    bus.suscribir(SolicitudPartnerRegistrada, "reglas_partner.evaluar", flujo.evaluar)
    bus.suscribir(ReglasDePartnerEvaluadas, "solicitudes.aplicar", flujo.aplicar)
    return flujo


def componer_flujo_sql(
    base: "Database",
    reloj: Reloj,
    identificadores: GeneradorIdentificadores,
    bus: BusEventos,
) -> FlujoInterno:
    from solicitudes_partner.config.persistencia import crear_uow_reglas, crear_uow_solicitudes

    return componer_flujo(
        lambda: crear_uow_solicitudes(base),
        lambda: crear_uow_reglas(base),
        reloj,
        identificadores,
        bus,
    )
