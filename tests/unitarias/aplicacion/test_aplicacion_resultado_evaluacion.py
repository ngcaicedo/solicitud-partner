from dataclasses import replace
from uuid import UUID

import pytest

from solicitudes_partner.modulos.solicitudes.aplicacion.excepciones import SolicitudNoEncontrada
from tests.unitarias.aplicacion.datos import Escenario
from tests.unitarias.dominio.datos import ID_SOLICITUD, resultado, solicitud_nueva
from tests.unitarias.dominio.datos_resultados import resultado_solicitud


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
    assert (
        actual is not None
        and actual.version == 2
        and actual.evaluacion == resultado_solicitud(aprobacion)
    )
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


@pytest.mark.parametrize("aprobacion", [False, True])
def test_traduccion_conserva_trazabilidad_con_tipos_propios(aprobacion: bool) -> None:
    from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
        Admisibilidad,
        MotivoRechazo,
        ResultadoEvaluacion,
        TipoRedProveedores,
    )

    escenario = Escenario()
    solicitud = solicitud_nueva(aprobacion)
    solicitud.retirar_eventos()
    escenario.solicitudes.estado.solicitudes.guardar(solicitud)
    evento = resultado(aprobacion)
    escenario.reloj.instante = evento.instante
    escenario.flujo.aplicar(evento)
    actual = escenario.solicitudes.estado.solicitudes.obtener(ID_SOLICITUD)
    assert actual is not None
    evaluacion = actual.evaluacion
    assert isinstance(evaluacion, ResultadoEvaluacion)
    assert evaluacion.id_evento == evento.id_evento
    assert evaluacion.instante == evento.instante
    assert evaluacion.id_evaluacion == evento.id_evaluacion
    assert evaluacion.id_solicitud == evento.id_solicitud
    assert evaluacion.id_partner == evento.id_partner
    assert evaluacion.version_solicitud == evento.version_solicitud
    assert evaluacion.id_politica == evento.id_politica
    assert evaluacion.version_politica == evento.version_politica
    assert type(evaluacion.resultado) is Admisibilidad
    assert evaluacion.resultado.value == evento.resultado.value
    if aprobacion:
        assert type(evaluacion.tipo_red) is TipoRedProveedores
        assert evento.tipo_red is not None
        assert evaluacion.tipo_red.value == evento.tipo_red.value
        assert evaluacion.motivo is None
    else:
        assert type(evaluacion.motivo) is MotivoRechazo
        assert evento.motivo is not None
        assert evaluacion.motivo.value == evento.motivo.value
        assert evaluacion.tipo_red is None


@pytest.mark.parametrize("campo", ["id_evento", "id_politica", "version_politica"])
def test_reentrega_con_origen_distinto_se_rechaza_tras_traducir(campo: str) -> None:
    escenario = Escenario()
    solicitud = solicitud_nueva()
    solicitud.retirar_eventos()
    escenario.solicitudes.estado.solicitudes.guardar(solicitud)
    evento = resultado()
    escenario.reloj.instante = evento.instante
    escenario.flujo.aplicar(evento)
    alternativa = {
        "id_evento": replace(evento, id_evento=UUID(int=99)),
        "id_politica": replace(evento, id_politica=UUID(int=99)),
        "version_politica": replace(evento, version_politica=2),
    }[campo]
    with pytest.raises(ValueError, match="ya tiene una evaluacion inicial"):
        escenario.flujo.aplicar(alternativa)
    assert escenario.solicitudes.confirmaciones == 1
    assert len(escenario.solicitudes.estado.salidas) == 1
