from solicitudes_partner.config.bootstrap import FlujoInterno, componer_flujo_sql
from solicitudes_partner.config.database import Database
from solicitudes_partner.seedwork.infraestructura.bus_eventos_local import BusEventosLocal
from solicitudes_partner.seedwork.infraestructura.identificadores import IdentificadoresAleatorios
from solicitudes_partner.seedwork.infraestructura.reloj import RelojActual


def flujo_sql(base: Database) -> FlujoInterno:
    return componer_flujo_sql(base, RelojActual(), IdentificadoresAleatorios(), BusEventosLocal())
