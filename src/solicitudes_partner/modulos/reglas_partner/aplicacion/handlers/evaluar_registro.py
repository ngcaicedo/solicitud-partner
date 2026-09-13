from collections.abc import Callable
from dataclasses import dataclass

from solicitudes_partner.modulos.reglas_partner.aplicacion.excepciones import ConflictoEvaluacion
from solicitudes_partner.modulos.reglas_partner.aplicacion.unidad_trabajo import UnidadTrabajoReglas
from solicitudes_partner.modulos.reglas_partner.dominio.servicios import evaluar_solicitud
from solicitudes_partner.modulos.solicitudes.dominio.eventos import (
    SolicitudPartnerRegistrada,
)
from solicitudes_partner.seedwork.aplicacion.identificadores import GeneradorIdentificadores
from solicitudes_partner.seedwork.aplicacion.reloj import Reloj


@dataclass(frozen=True)
class EvaluarRegistroHandler:
    crear_unidad: Callable[[], UnidadTrabajoReglas]
    reloj: Reloj
    identificadores: GeneradorIdentificadores

    def __call__(self, registro: SolicitudPartnerRegistrada) -> None:
        with self.crear_unidad() as unidad:
            existente = unidad.evaluaciones.obtener_por_solicitud(registro.id_solicitud)
            if existente is not None:
                if unidad.evaluaciones.obtener_origen(registro.id_solicitud) != registro:
                    raise ConflictoEvaluacion("La solicitud ya fue evaluada con otro registro")
                return
            politica = unidad.politicas.obtener(registro.datos.id_partner)
            evaluacion = evaluar_solicitud(
                registro,
                politica,
                id_evaluacion=self.identificadores.generar(),
                id_evento=self.identificadores.generar(),
                instante=self.reloj.ahora(),
            )
            unidad.evaluaciones.guardar(evaluacion)
            unidad.evaluaciones.guardar_origen(registro)
            unidad.registrar_salida(evaluacion.evento)
            unidad.confirmar()
