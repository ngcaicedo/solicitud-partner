from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from solicitudes_partner.modulos.reglas_partner.dominio.eventos import (
    ReglasDePartnerEvaluadas,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.excepciones import SolicitudNoEncontrada
from solicitudes_partner.modulos.solicitudes.aplicacion.unidad_trabajo import (
    UnidadTrabajoSolicitudes,
)
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
    Admisibilidad,
    MotivoRechazo,
    ResultadoEvaluacion,
    TipoRedProveedores,
)
from solicitudes_partner.seedwork.aplicacion.identificadores import GeneradorIdentificadores
from solicitudes_partner.seedwork.aplicacion.reintentos import reintentar_colision
from solicitudes_partner.seedwork.aplicacion.reloj import Reloj


@dataclass(frozen=True)
class AplicarResultadoEvaluacionHandler:
    consumidor: ClassVar[str] = "solicitudes.aplicar"
    crear_unidad: Callable[[], UnidadTrabajoSolicitudes]
    reloj: Reloj
    identificadores: GeneradorIdentificadores

    @reintentar_colision
    def __call__(self, evento: ReglasDePartnerEvaluadas) -> None:
        with self.crear_unidad() as unidad:
            solicitud = unidad.solicitudes.obtener(evento.id_solicitud)
            if solicitud is None:
                raise SolicitudNoEncontrada("No existe la solicitud evaluada")
            evento.__post_init__()
            resultado = ResultadoEvaluacion(
                id_evento=evento.id_evento,
                instante=evento.instante,
                id_evaluacion=evento.id_evaluacion,
                id_solicitud=evento.id_solicitud,
                id_partner=evento.id_partner,
                version_solicitud=evento.version_solicitud,
                id_politica=evento.id_politica,
                version_politica=evento.version_politica,
                resultado=Admisibilidad(evento.resultado.value),
                tipo_red=TipoRedProveedores(evento.tipo_red.value) if evento.tipo_red else None,
                motivo=MotivoRechazo(evento.motivo.value) if evento.motivo else None,
            )
            solicitud.aplicar_resultado_evaluacion(
                resultado,
                id_evento=self.identificadores.generar(),
                instante=self.reloj.ahora(),
            )
            if not unidad.preparar_entrada(self.consumidor, evento):
                return
            salidas = solicitud.retirar_eventos()
            if not salidas:
                unidad.confirmar()
                return
            unidad.solicitudes.guardar(solicitud)
            for salida in salidas:
                unidad.registrar_salida(salida)
            unidad.confirmar()
