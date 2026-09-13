from collections.abc import Callable
from dataclasses import dataclass

from solicitudes_partner.modulos.reglas_partner.dominio.eventos import (
    ReglasDePartnerEvaluadas,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.excepciones import SolicitudNoEncontrada
from solicitudes_partner.modulos.solicitudes.aplicacion.unidad_trabajo import (
    UnidadTrabajoSolicitudes,
)
from solicitudes_partner.seedwork.aplicacion.identificadores import GeneradorIdentificadores
from solicitudes_partner.seedwork.aplicacion.reloj import Reloj


@dataclass(frozen=True)
class AplicarResultadoEvaluacionHandler:
    crear_unidad: Callable[[], UnidadTrabajoSolicitudes]
    reloj: Reloj
    identificadores: GeneradorIdentificadores

    def __call__(self, evento: ReglasDePartnerEvaluadas) -> None:
        with self.crear_unidad() as unidad:
            solicitud = unidad.solicitudes.obtener(evento.id_solicitud)
            if solicitud is None:
                raise SolicitudNoEncontrada("No existe la solicitud evaluada")
            solicitud.aplicar_resultado_evaluacion(
                evento,
                id_evento=self.identificadores.generar(),
                instante=self.reloj.ahora(),
            )
            salidas = solicitud.retirar_eventos()
            if not salidas:
                return
            unidad.solicitudes.guardar(solicitud)
            for salida in salidas:
                unidad.registrar_salida(salida)
            unidad.confirmar()
