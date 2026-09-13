from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from solicitudes_partner.config.rutas import DESTINOS_EXTERNOS, DESTINOS_INTERNOS
from solicitudes_partner.config.serializacion import decodificar_evento
from solicitudes_partner.seedwork.infraestructura.bus_eventos_local import BusEventosLocal
from solicitudes_partner.seedwork.infraestructura.identificadores import IdentificadoresAleatorios
from solicitudes_partner.seedwork.infraestructura.publicador_bus import PublicadorBus
from solicitudes_partner.seedwork.infraestructura.reloj import RelojActual

if TYPE_CHECKING:
    from solicitudes_partner.config.database import Database
    from solicitudes_partner.config.settings import Settings
    from solicitudes_partner.seedwork.infraestructura.despacho_outbox import DespachadorOutbox

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
    bus.suscribir(SolicitudPartnerRegistrada, flujo.evaluar.consumidor, flujo.evaluar)
    bus.suscribir(ReglasDePartnerEvaluadas, flujo.aplicar.consumidor, flujo.aplicar)
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


def componer_despacho_interno(base: "Database") -> "DespachadorOutbox":
    from solicitudes_partner.seedwork.infraestructura.despacho_outbox import DespachadorOutbox
    from solicitudes_partner.seedwork.infraestructura.outbox import RepositorioOutbox

    bus = BusEventosLocal()
    componer_flujo_sql(base, RelojActual(), IdentificadoresAleatorios(), bus)
    return DespachadorOutbox(
        RepositorioOutbox(base.session_factory, DESTINOS_INTERNOS),
        PublicadorBus(bus, decodificar_evento),
        f"interno-{uuid4()}",
    )


def componer_publicacion(
    base: "Database", configuracion: "Settings"
) -> tuple["DespachadorOutbox", Callable[[], None]]:
    from pulsar.schema import AvroSchema

    from solicitudes_partner.modulos.solicitudes.infraestructura.esquemas.v1.eventos import (
        SolicitudListaV1,
    )
    from solicitudes_partner.modulos.solicitudes.infraestructura.mapeador_integracion import (
        evento_integracion,
    )
    from solicitudes_partner.seedwork.infraestructura.despacho_outbox import DespachadorOutbox
    from solicitudes_partner.seedwork.infraestructura.outbox import RepositorioOutbox
    from solicitudes_partner.seedwork.infraestructura.publicador_pulsar import PublicadorPulsar

    publicador = PublicadorPulsar(
        configuracion.pulsar_url,
        configuracion.topico_solicitudes,
        AvroSchema(SolicitudListaV1),
        lambda documento: evento_integracion(decodificar_evento(documento)),
    )
    despacho = DespachadorOutbox(
        RepositorioOutbox(base.session_factory, DESTINOS_EXTERNOS),
        publicador,
        f"integracion-{uuid4()}",
    )
    return despacho, publicador.cerrar
