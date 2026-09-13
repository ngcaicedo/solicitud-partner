from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from typing import Any, cast
from uuid import UUID

import pytest

from solicitudes_partner.modulos.reglas_partner.dominio.excepciones import (
    ErrorConfiguracionPolitica,
)
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import (
    MotivoRechazo,
    PoliticaPartner,
    ResultadoEvaluacion,
    TipoRedProveedores,
)
from solicitudes_partner.modulos.reglas_partner.dominio.servicios import evaluar_solicitud
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import TipoSolicitud

from .datos import ID_EVALUACION, INSTANTE, politica, registro


@pytest.mark.parametrize("red", list(TipoRedProveedores))
@pytest.mark.parametrize(
    ("tipo", "aprobacion", "resultado_esperado"),
    [
        (TipoSolicitud.SINIESTRO, True, ResultadoEvaluacion.ADMISIBLE),
        (TipoSolicitud.SINIESTRO, False, ResultadoEvaluacion.NO_ADMISIBLE),
        (TipoSolicitud.INSTALACION, None, ResultadoEvaluacion.ADMISIBLE),
        (TipoSolicitud.INSTALACION, False, ResultadoEvaluacion.ADMISIBLE),
    ],
)
def test_politica_aplica_aprobacion_solo_a_siniestros_y_conserva_red(
    red: TipoRedProveedores,
    tipo: TipoSolicitud,
    aprobacion: bool | None,
    resultado_esperado: ResultadoEvaluacion,
) -> None:
    configuracion = politica(red)
    solicitud = registro(aprobacion, tipo)
    evaluacion = evaluar_solicitud(
        solicitud,
        configuracion,
        id_evaluacion=ID_EVALUACION,
        id_evento=UUID(int=11),
        instante=INSTANTE + timedelta(seconds=1),
    )
    evento = evaluacion.evento
    assert evaluacion.id == ID_EVALUACION
    assert evento.id_solicitud == solicitud.id_solicitud
    assert evento.id_partner == solicitud.datos.id_partner
    assert evento.version_solicitud == 1
    assert evento.id_politica == configuracion.id
    assert evento.version_politica == configuracion.version
    assert evento.resultado is resultado_esperado
    assert evento.instante == INSTANTE + timedelta(seconds=1)
    if resultado_esperado is ResultadoEvaluacion.ADMISIBLE:
        assert evento.tipo_red is red
        assert evento.motivo is None
    else:
        assert evento.tipo_red is None
        assert evento.motivo is MotivoRechazo.APROBACION_PREVIA_REQUERIDA


@pytest.mark.parametrize("aprobacion", [True, False])
@pytest.mark.parametrize("ajena", [True, False])
def test_configuracion_se_valida_antes_de_decidir_rechazo(aprobacion: bool, ajena: bool) -> None:
    configuracion = replace(politica(), id_partner=UUID(int=999)) if ajena else None
    with pytest.raises(ErrorConfiguracionPolitica):
        evaluar_solicitud(
            registro(aprobacion),
            configuracion,
            id_evaluacion=ID_EVALUACION,
            id_evento=UUID(int=11),
            instante=INSTANTE,
        )


@pytest.mark.parametrize(
    "cambio",
    [{"tipo_red": "DESCONOCIDA"}, {"version": 0}, {"version": True}, {"id_partner": ""}],
)
def test_politica_invalida_no_puede_construirse(cambio: dict[str, Any]) -> None:
    with pytest.raises(ErrorConfiguracionPolitica):
        replace(politica(), **cambio)


def test_politica_es_inmutable_y_evaluacion_conserva_version_original() -> None:
    original = politica()
    evaluacion = evaluar_solicitud(
        registro(),
        original,
        id_evaluacion=ID_EVALUACION,
        id_evento=UUID(int=11),
        instante=INSTANTE,
    )
    actualizada = replace(original, version=2, tipo_red=TipoRedProveedores.HOMOLOGADA_PARTNER)
    assert actualizada.version == 2
    assert evaluacion.evento.version_politica == 1
    assert evaluacion.evento.tipo_red is TipoRedProveedores.GENERAL_HDA
    with pytest.raises(FrozenInstanceError):
        original.tipo_red = actualizada.tipo_red  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        evaluacion.evento = evaluacion.evento  # type: ignore[misc]


def test_evaluador_rechaza_objeto_que_no_es_politica() -> None:
    with pytest.raises(ErrorConfiguracionPolitica):
        evaluar_solicitud(
            registro(),
            cast(PoliticaPartner, object()),
            id_evaluacion=ID_EVALUACION,
            id_evento=UUID(int=11),
            instante=INSTANTE,
        )
