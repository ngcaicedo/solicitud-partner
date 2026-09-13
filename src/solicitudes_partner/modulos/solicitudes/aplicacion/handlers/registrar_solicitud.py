from collections.abc import Callable
from dataclasses import dataclass

from solicitudes_partner.modulos.solicitudes.aplicacion.comandos import RegistrarSolicitudPartner
from solicitudes_partner.modulos.solicitudes.aplicacion.confirmaciones import (
    ConfirmacionRegistroSolicitud,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.excepciones import ConflictoRegistro
from solicitudes_partner.modulos.solicitudes.aplicacion.unidad_trabajo import (
    UnidadTrabajoSolicitudes,
)
from solicitudes_partner.modulos.solicitudes.dominio.entidades import SolicitudPartner
from solicitudes_partner.seedwork.aplicacion.identificadores import GeneradorIdentificadores
from solicitudes_partner.seedwork.aplicacion.reintentos import reintentar_colision
from solicitudes_partner.seedwork.aplicacion.reloj import Reloj


@dataclass(frozen=True)
class RegistrarSolicitudHandler:
    crear_unidad: Callable[[], UnidadTrabajoSolicitudes]
    reloj: Reloj
    identificadores: GeneradorIdentificadores

    @reintentar_colision
    def __call__(self, comando: RegistrarSolicitudPartner) -> ConfirmacionRegistroSolicitud:
        with self.crear_unidad() as unidad:
            datos = comando.datos
            existente = unidad.solicitudes.obtener_por_referencia(
                datos.id_partner, datos.referencia_externa
            )
            if existente is not None:
                if existente.datos != datos:
                    raise ConflictoRegistro("La referencia ya tiene otros datos de solicitud")
                return ConfirmacionRegistroSolicitud(id_solicitud=existente.id)
            solicitud = SolicitudPartner.registrar(
                id=self.identificadores.generar(),
                datos=datos,
                id_evento=self.identificadores.generar(),
                instante=self.reloj.ahora(),
            )
            unidad.solicitudes.guardar(solicitud)
            for evento in solicitud.retirar_eventos():
                unidad.registrar_salida(evento)
            unidad.confirmar()
            return ConfirmacionRegistroSolicitud(id_solicitud=solicitud.id)
