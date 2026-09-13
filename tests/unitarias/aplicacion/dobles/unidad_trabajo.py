from copy import deepcopy
from dataclasses import dataclass, field
from types import TracebackType
from typing import Self
from uuid import UUID

from solicitudes_partner.seedwork.aplicacion.bus_eventos import BusEventos
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio
from tests.unitarias.aplicacion.dobles.repositorios import (
    RepositorioEvaluacionesMemoria,
    RepositorioPoliticasMemoria,
    RepositorioSolicitudesMemoria,
)


@dataclass
class EstadoSolicitudes:
    solicitudes: RepositorioSolicitudesMemoria = field(
        default_factory=RepositorioSolicitudesMemoria
    )
    salidas: list[EventoDominio] = field(default_factory=list)
    entradas: dict[tuple[str, UUID], EventoDominio] = field(default_factory=dict)


@dataclass
class EstadoReglas:
    evaluaciones: RepositorioEvaluacionesMemoria = field(
        default_factory=RepositorioEvaluacionesMemoria
    )
    politicas: RepositorioPoliticasMemoria = field(default_factory=RepositorioPoliticasMemoria)
    salidas: list[EventoDominio] = field(default_factory=list)
    entradas: dict[tuple[str, UUID], EventoDominio] = field(default_factory=dict)


@dataclass
class AlmacenMemoria[Estado: (EstadoSolicitudes, EstadoReglas)]:
    estado: Estado
    fallar_confirmacion: bool = False
    confirmaciones: int = 0

    def transferir_salidas(self, bus: BusEventos) -> None:
        while self.estado.salidas:
            bus.publicar(self.estado.salidas[0])
            self.estado.salidas.pop(0)


class UnidadTrabajoMemoria[Estado: (EstadoSolicitudes, EstadoReglas)]:
    def __init__(self, almacen: AlmacenMemoria[Estado]) -> None:
        self.almacen: AlmacenMemoria[Estado] = almacen
        self.estado: Estado = deepcopy(almacen.estado)
        self.activa = False

    def __enter__(self) -> Self:
        if self.activa:
            raise RuntimeError("Unidad de trabajo ya activa")
        self.estado = deepcopy(self.almacen.estado)
        self.activa = True
        return self

    def __exit__(
        self,
        tipo_error: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        self.revertir()

    def registrar_salida(self, evento: EventoDominio) -> None:
        self._verificar_activa()
        self.estado.salidas.append(evento)

    def preparar_entrada(self, consumidor: str, evento: EventoDominio) -> bool:
        self._verificar_activa()
        clave = (consumidor, evento.id_evento)
        anterior = self.estado.entradas.get(clave)
        if anterior is not None:
            if anterior != evento:
                raise ValueError("La entrada ya tiene otro contenido")
            return False
        self.estado.entradas[clave] = evento
        return True

    def confirmar(self) -> None:
        self._verificar_activa()
        if self.almacen.fallar_confirmacion:
            raise RuntimeError("Fallo de confirmacion")
        self.almacen.estado = deepcopy(self.estado)
        self.almacen.confirmaciones += 1
        self.activa = False

    def revertir(self) -> None:
        self.estado = deepcopy(self.almacen.estado)
        self.activa = False

    def _verificar_activa(self) -> None:
        if not self.activa:
            raise RuntimeError("Unidad de trabajo inactiva")


class UnidadTrabajoSolicitudesMemoria(UnidadTrabajoMemoria[EstadoSolicitudes]):
    @property
    def solicitudes(self) -> RepositorioSolicitudesMemoria:
        return self.estado.solicitudes


class UnidadTrabajoReglasMemoria(UnidadTrabajoMemoria[EstadoReglas]):
    @property
    def evaluaciones(self) -> RepositorioEvaluacionesMemoria:
        return self.estado.evaluaciones

    @property
    def politicas(self) -> RepositorioPoliticasMemoria:
        return self.estado.politicas
