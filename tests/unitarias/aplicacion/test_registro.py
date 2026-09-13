from dataclasses import replace
from typing import Any
from uuid import UUID

import pytest

from solicitudes_partner.modulos.solicitudes.aplicacion.comandos import RegistrarSolicitudPartner
from solicitudes_partner.modulos.solicitudes.aplicacion.excepciones import ConflictoRegistro
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import TipoSolicitud
from tests.unitarias.aplicacion.datos import Escenario
from tests.unitarias.dominio.datos import datos_solicitud


def test_confirmacion_confirma_registro_sin_evaluar_ni_despachar() -> None:
    escenario = Escenario()
    comando = RegistrarSolicitudPartner(datos=datos_solicitud())
    confirmacion = escenario.flujo.registrar(comando)
    assert confirmacion.recepcion_confirmada
    solicitud = escenario.solicitudes.estado.solicitudes.obtener(confirmacion.id_solicitud)
    assert solicitud is not None and solicitud.version == 1
    assert solicitud.eventos_pendientes == ()
    assert len(escenario.solicitudes.estado.salidas) == 1
    assert escenario.reglas.estado.evaluaciones.evaluaciones == {}
    assert escenario.bus.publicados == ()
    assert escenario.solicitudes.confirmaciones == 1


@pytest.mark.parametrize("finalizada", [False, True])
@pytest.mark.parametrize("aprobacion", [False, True])
def test_reintento_conserva_confirmacion_y_no_genera_efectos(
    finalizada: bool, aprobacion: bool
) -> None:
    escenario = Escenario()
    comando = RegistrarSolicitudPartner(datos=datos_solicitud(aprobacion))
    confirmacion = escenario.flujo.registrar(comando)
    if finalizada:
        escenario.completar()
    confirmaciones = escenario.solicitudes.confirmaciones
    ids = escenario.ids.siguiente
    assert escenario.flujo.registrar(replace(comando)) == confirmacion
    assert escenario.solicitudes.confirmaciones == confirmaciones
    assert escenario.ids.siguiente == ids
    assert len(escenario.solicitudes.estado.solicitudes.solicitudes) == 1


@pytest.mark.parametrize(
    "campo,valor",
    [("categoria", "otra"), ("tipo", TipoSolicitud.INSTALACION), ("aprobacion_previa", False)],
)
def test_misma_clave_con_otro_contenido_es_conflicto(campo: str, valor: Any) -> None:
    escenario = Escenario()
    datos = datos_solicitud()
    escenario.flujo.registrar(RegistrarSolicitudPartner(datos=datos))
    with pytest.raises(ConflictoRegistro):
        escenario.flujo.registrar(RegistrarSolicitudPartner(datos=replace(datos, **{campo: valor})))
    assert escenario.solicitudes.confirmaciones == 1
    assert len(escenario.solicitudes.estado.salidas) == 1


def test_instalacion_con_distinta_aprobacion_cambia_contenido() -> None:
    escenario = Escenario()
    datos = datos_solicitud(None, TipoSolicitud.INSTALACION)
    escenario.flujo.registrar(RegistrarSolicitudPartner(datos=datos))
    with pytest.raises(ConflictoRegistro):
        escenario.flujo.registrar(
            RegistrarSolicitudPartner(datos=replace(datos, aprobacion_previa=False))
        )


@pytest.mark.parametrize(
    "cambio",
    [
        {"id_partner": UUID(int=999)},
        {"referencia_externa": "sin-100"},
        {"referencia_externa": "SIN-100 "},
    ],
)
def test_claves_distintas_no_se_normalizan(cambio: dict[str, Any]) -> None:
    escenario = Escenario()
    datos = datos_solicitud()
    primero = escenario.flujo.registrar(RegistrarSolicitudPartner(datos=datos))
    segundo = escenario.flujo.registrar(RegistrarSolicitudPartner(datos=replace(datos, **cambio)))
    assert primero.id_solicitud != segundo.id_solicitud


def test_fallo_confirmacion_no_devuelve_confirmacion_ni_publica() -> None:
    escenario = Escenario()
    escenario.solicitudes.fallar_confirmacion = True
    with pytest.raises(RuntimeError, match="Fallo de confirmacion"):
        escenario.flujo.registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
    assert escenario.solicitudes.estado.solicitudes.solicitudes == {}
    assert escenario.solicitudes.estado.salidas == []
    assert escenario.bus.publicados == ()
