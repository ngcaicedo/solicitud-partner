from datetime import UTC, datetime
from uuid import UUID, uuid4

from solicitudes_partner.config.bootstrap import FlujoInterno, componer_flujo_sql
from solicitudes_partner.config.database import Database
from solicitudes_partner.seedwork.infraestructura.bus_eventos_local import BusEventosLocal


class RelojActual:
    def ahora(self) -> datetime:
        return datetime.now(UTC)


class IdentificadoresAleatorios:
    def generar(self) -> UUID:
        return uuid4()


def flujo_sql(base: Database) -> FlujoInterno:
    return componer_flujo_sql(base, RelojActual(), IdentificadoresAleatorios(), BusEventosLocal())
