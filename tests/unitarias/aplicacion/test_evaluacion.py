from dataclasses import replace
from datetime import timedelta
from uuid import UUID

import pytest

from solicitudes_partner.modulos.reglas_partner.aplicacion.excepciones import ConflictoEvaluacion
from solicitudes_partner.modulos.reglas_partner.dominio.excepciones import (
    ErrorConfiguracionPolitica,
)
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import (
    ResultadoEvaluacion,
    TipoRedProveedores,
)
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import TipoSolicitud
from tests.unitarias.aplicacion.datos import Escenario
from tests.unitarias.dominio.datos import ID_PARTNER, politica, registro


@pytest.mark.parametrize("red", list(TipoRedProveedores))
@pytest.mark.parametrize(
    "tipo,aprobacion",
    [
        (TipoSolicitud.SINIESTRO, True),
        (TipoSolicitud.SINIESTRO, False),
        (TipoSolicitud.INSTALACION, None),
        (TipoSolicitud.INSTALACION, False),
    ],
)
def test_evaluacion_guarda_modelo_origen_y_evento(
    red: TipoRedProveedores, tipo: TipoSolicitud, aprobacion: bool | None
) -> None:
    escenario = Escenario()
    escenario.reglas.estado.politicas.politicas[ID_PARTNER] = politica(red)
    origen = registro(aprobacion, tipo)
    escenario.flujo.evaluar(origen)
    evaluacion = escenario.reglas.estado.evaluaciones.obtener_por_solicitud(origen.id_solicitud)
    assert evaluacion is not None
    assert escenario.reglas.estado.evaluaciones.obtener_origen(origen.id_solicitud) == origen
    assert escenario.reglas.estado.salidas == [evaluacion.evento]
    rechazado = tipo is TipoSolicitud.SINIESTRO and aprobacion is False
    assert evaluacion.evento.resultado is (
        ResultadoEvaluacion.NO_ADMISIBLE if rechazado else ResultadoEvaluacion.ADMISIBLE
    )
    assert evaluacion.evento.tipo_red == (None if rechazado else red)


@pytest.mark.parametrize("retirar", [False, True])
def test_reentrega_no_consulta_politica_actual_ni_genera_ids(retirar: bool) -> None:
    escenario = Escenario()
    origen = registro()
    escenario.flujo.evaluar(origen)
    original = escenario.reglas.estado.salidas.copy()
    if retirar:
        escenario.reglas.estado.politicas.politicas.clear()
    else:
        escenario.reglas.estado.politicas.politicas[ID_PARTNER] = replace(
            politica(), version=2, tipo_red=TipoRedProveedores.HOMOLOGADA_PARTNER
        )
    escenario.reglas.estado.politicas.consultas = 0
    siguiente = escenario.ids.siguiente
    escenario.flujo.evaluar(replace(origen))
    assert escenario.reglas.estado.salidas == original
    assert escenario.reglas.confirmaciones == 1
    assert escenario.reglas.estado.politicas.consultas == 0
    assert escenario.ids.siguiente == siguiente


@pytest.mark.parametrize("cambio", ["evento", "instante", "datos"])
def test_registro_incompatible_no_sustituye_evaluacion(cambio: str) -> None:
    escenario = Escenario()
    origen = registro()
    escenario.flujo.evaluar(origen)
    alternativo = {
        "evento": replace(origen, id_evento=UUID(int=700)),
        "instante": replace(origen, instante=origen.instante + timedelta(seconds=1)),
        "datos": replace(origen, datos=replace(origen.datos, categoria="otra")),
    }[cambio]
    with pytest.raises(ConflictoEvaluacion):
        escenario.flujo.evaluar(alternativo)
    assert escenario.reglas.confirmaciones == 1
    assert len(escenario.reglas.estado.evaluaciones.evaluaciones) == 1


@pytest.mark.parametrize("configuracion", ["ausente", "ajena", "invalida"])
@pytest.mark.parametrize("aprobacion", [False, True])
def test_error_configuracion_no_confirma_evaluacion(configuracion: str, aprobacion: bool) -> None:
    escenario = Escenario()
    politicas = escenario.reglas.estado.politicas.politicas
    if configuracion == "ausente":
        politicas.clear()
    elif configuracion == "ajena":
        politicas[ID_PARTNER] = replace(politica(), id_partner=UUID(int=999))
    else:
        object.__setattr__(politicas[ID_PARTNER], "tipo_red", "INVALIDA")
    with pytest.raises(ErrorConfiguracionPolitica):
        escenario.flujo.evaluar(registro(aprobacion))
    assert escenario.reglas.estado.evaluaciones.evaluaciones == {}
    assert escenario.reglas.estado.salidas == []
    politicas[ID_PARTNER] = politica()
    escenario.flujo.evaluar(registro(aprobacion))
    assert escenario.reglas.confirmaciones == 1
