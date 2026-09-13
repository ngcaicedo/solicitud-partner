from dataclasses import dataclass, field

from solicitudes_partner.config.bootstrap import FlujoInterno, componer_flujo
from solicitudes_partner.seedwork.infraestructura.bus_eventos_local import BusEventosLocal
from tests.unitarias.aplicacion.dobles.identificadores import IdentificadoresSecuenciales
from tests.unitarias.aplicacion.dobles.reloj import RelojSecuencial
from tests.unitarias.aplicacion.dobles.unidad_trabajo import (
    AlmacenMemoria,
    EstadoReglas,
    EstadoSolicitudes,
    UnidadTrabajoReglasMemoria,
    UnidadTrabajoSolicitudesMemoria,
)
from tests.unitarias.dominio.datos import ID_PARTNER, politica


@dataclass
class Escenario:
    solicitudes: AlmacenMemoria[EstadoSolicitudes] = field(
        default_factory=lambda: AlmacenMemoria(EstadoSolicitudes())
    )
    reglas: AlmacenMemoria[EstadoReglas] = field(
        default_factory=lambda: AlmacenMemoria(EstadoReglas())
    )
    reloj: RelojSecuencial = field(default_factory=RelojSecuencial)
    ids: IdentificadoresSecuenciales = field(default_factory=IdentificadoresSecuenciales)
    bus: BusEventosLocal = field(default_factory=BusEventosLocal)
    flujo: FlujoInterno = field(init=False)

    def __post_init__(self) -> None:
        self.reglas.estado.politicas.politicas[ID_PARTNER] = politica()
        self.flujo = componer_flujo(
            lambda: UnidadTrabajoSolicitudesMemoria(self.solicitudes),
            lambda: UnidadTrabajoReglasMemoria(self.reglas),
            self.reloj,
            self.ids,
            self.bus,
        )

    def transferir(self) -> None:
        self.solicitudes.transferir_salidas(self.bus)
        self.reglas.transferir_salidas(self.bus)

    def completar(self) -> None:
        self.transferir()
        while self.bus.despachar_siguiente():
            self.transferir()
