from collections.abc import Callable
from typing import Protocol

from solicitudes_partner.seedwork.dominio.eventos import EventoDominio


class BusEventos(Protocol):
    def publicar(self, evento: EventoDominio) -> None: ...

    def suscribir[Evento: EventoDominio](
        self, tipo: type[Evento], consumidor: str, manejador: Callable[[Evento], None]
    ) -> None: ...
