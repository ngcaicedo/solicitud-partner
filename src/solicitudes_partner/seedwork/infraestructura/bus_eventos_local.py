from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from solicitudes_partner.seedwork.dominio.eventos import EventoDominio


@dataclass(frozen=True)
class EntregaEvento:
    evento: EventoDominio
    consumidor: str


class BusEventosLocal:
    def __init__(self) -> None:
        self._suscripciones: dict[
            type[EventoDominio], dict[str, Callable[[EventoDominio], None]]
        ] = {}
        self._pendientes: deque[EntregaEvento] = deque()
        self._publicados: list[EventoDominio] = []
        self._sin_suscriptores: list[EventoDominio] = []
        self._despachando = False

    @property
    def pendientes(self) -> tuple[EntregaEvento, ...]:
        return tuple(self._pendientes)

    @property
    def publicados(self) -> tuple[EventoDominio, ...]:
        return tuple(self._publicados)

    @property
    def sin_suscriptores(self) -> tuple[EventoDominio, ...]:
        return tuple(self._sin_suscriptores)

    def suscribir[Evento: EventoDominio](
        self, tipo: type[Evento], consumidor: str, manejador: Callable[[Evento], None]
    ) -> None:
        suscripciones = self._suscripciones.setdefault(tipo, {})
        if not consumidor.strip() or consumidor in suscripciones:
            raise ValueError("Identidad de consumidor vacia o ya suscrita")

        def recibir(evento: EventoDominio) -> None:
            if not isinstance(evento, tipo):
                raise TypeError("Tipo de evento incompatible")
            manejador(evento)

        suscripciones[consumidor] = recibir

    def publicar(self, evento: EventoDominio) -> None:
        self._publicados.append(evento)
        consumidores = self._suscripciones.get(type(evento), {})
        self._pendientes.extend(EntregaEvento(evento, consumidor) for consumidor in consumidores)
        if not consumidores:
            self._sin_suscriptores.append(evento)

    def despachar_siguiente(self) -> bool:
        if self._despachando:
            raise RuntimeError("No se permite despacho recursivo")
        if not self._pendientes:
            return False
        entrega = self._pendientes[0]
        self._despachando = True
        try:
            self._suscripciones[type(entrega.evento)][entrega.consumidor](entrega.evento)
            self._pendientes.popleft()
        finally:
            self._despachando = False
        return True

    def entregar(self, evento: EventoDominio, consumidor: str) -> None:
        if self._despachando:
            raise RuntimeError("No se permite despacho recursivo")
        manejador = self._suscripciones.get(type(evento), {}).get(consumidor)
        if manejador is None:
            raise ValueError("No hay suscriptor para la entrega interna")
        self._despachando = True
        try:
            manejador(evento)
        finally:
            self._despachando = False
