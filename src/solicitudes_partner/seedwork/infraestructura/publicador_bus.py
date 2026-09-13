from collections.abc import Callable
from dataclasses import dataclass

from solicitudes_partner.seedwork.aplicacion.publicacion import Publicacion
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio
from solicitudes_partner.seedwork.infraestructura.bus_eventos_local import BusEventosLocal
from solicitudes_partner.seedwork.infraestructura.serializacion import Documento


@dataclass(frozen=True)
class PublicadorBus:
    bus: BusEventosLocal
    decodificar: Callable[[Documento], EventoDominio]

    def publicar(self, publicacion: Publicacion) -> bool:
        evento = self.decodificar(publicacion.documento)
        if evento.id_evento != publicacion.id_evento:
            raise ValueError("Identidad de entrega incompatible con evento")
        self.bus.entregar(evento, publicacion.destino)
        return True
