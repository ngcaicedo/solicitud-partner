from dataclasses import replace
from uuid import UUID

import pytest

from solicitudes_partner.modulos.solicitudes.aplicacion.excepciones import SolicitudNoEncontrada
from tests.unitarias.aplicacion.datos import Escenario
from tests.unitarias.dominio.datos import ID_SOLICITUD, resultado, solicitud_nueva


@pytest.mark.parametrize("aprobacion", [False, True])
def test_aplicar_resultado_y_repetir_no_duplica_transicion(aprobacion: bool) -> None:
    escenario = Escenario()
    solicitud = solicitud_nueva(aprobacion)
    solicitud.retirar_eventos()
    escenario.solicitudes.estado.solicitudes.guardar(solicitud)
    evento = resultado(aprobacion)
    escenario.reloj.instante = evento.instante
    escenario.flujo.aplicar(evento)
    escenario.flujo.aplicar(replace(evento))
    actual = escenario.solicitudes.estado.solicitudes.obtener(ID_SOLICITUD)
    assert actual is not None and actual.version == 2 and actual.evaluacion == evento
    assert len(escenario.solicitudes.estado.salidas) == 1
    assert escenario.solicitudes.confirmaciones == 1


@pytest.mark.parametrize("cambio", ["partner", "version", "otra_evaluacion", "resultado"])
def test_resultado_incompatible_no_corrompe_estado(cambio: str) -> None:
    escenario = Escenario()
    solicitud = solicitud_nueva()
    solicitud.retirar_eventos()
    escenario.solicitudes.estado.solicitudes.guardar(solicitud)
    evento = resultado()
    escenario.reloj.instante = evento.instante
    if cambio in {"otra_evaluacion", "resultado"}:
        escenario.flujo.aplicar(evento)
    alternativa = {
        "partner": replace(evento, id_partner=UUID(int=99)),
        "version": replace(evento, version_solicitud=2),
        "otra_evaluacion": replace(evento, id_evaluacion=UUID(int=99)),
        "resultado": resultado(False),
    }[cambio]
    anteriores = escenario.solicitudes.estado.salidas.copy()
    with pytest.raises(ValueError):
        escenario.flujo.aplicar(alternativa)
    assert escenario.solicitudes.estado.salidas == anteriores
    actual = escenario.solicitudes.estado.solicitudes.obtener(ID_SOLICITUD)
    assert actual is not None
    assert actual.version == (2 if cambio in {"otra_evaluacion", "resultado"} else 1)


def test_resultado_de_solicitud_inexistente_no_la_crea() -> None:
    escenario = Escenario()
    with pytest.raises(SolicitudNoEncontrada):
        escenario.flujo.aplicar(resultado())
    assert escenario.solicitudes.estado.solicitudes.solicitudes == {}
