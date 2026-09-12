from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest

from solicitudes_partner.modulos.reglas_partner.contratos import (
    MotivoRechazo,
    ResultadoEvaluacion,
    TipoRedProveedores,
)
from solicitudes_partner.modulos.solicitudes.contratos import (
    SolicitudPartnerListaParaAtencion,
    SolicitudPartnerRechazada,
    SolicitudPartnerRegistrada,
)
from solicitudes_partner.modulos.solicitudes.dominio.entidades import SolicitudPartner
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import EstadoSolicitud

from .datos import ID_SOLICITUD, INSTANTE, datos_solicitud, resultado, solicitud_nueva


def test_registro_crea_identidad_estado_y_evento_inmutable() -> None:
    solicitud = solicitud_nueva()
    assert solicitud.id == ID_SOLICITUD
    assert solicitud.estado is EstadoSolicitud.RECIBIDA
    assert solicitud.version == 1
    assert solicitud.evaluacion is None
    assert len(solicitud.eventos_pendientes) == 1
    evento = solicitud.eventos_pendientes[0]
    assert isinstance(evento, SolicitudPartnerRegistrada)
    assert evento.datos == datos_solicitud()
    assert evento.id_evento == UUID(int=10)
    assert evento.instante == INSTANTE
    for objeto, atributo, valor in [
        (solicitud, "id", UUID(int=999)),
        (solicitud, "estado", EstadoSolicitud.RECHAZADA),
        (evento, "version_solicitud", 99),
        (evento.datos, "referencia_externa", "OTRA"),
    ]:
        with pytest.raises(FrozenInstanceError):
            setattr(objeto, atributo, valor)


@pytest.mark.parametrize(
    "cambio",
    [
        {"referencia_externa": ""},
        {"referencia_externa": "   "},
        {"categoria": ""},
        {"categoria": []},
        {"id_partner": "partner"},
        {"tipo": "SINIESTRO"},
        {"aprobacion_previa": None},
        {"aprobacion_previa": "false"},
        {"aprobacion_previa": 1},
    ],
)
def test_datos_invalidos_se_rechazan_antes_del_registro(cambio: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        replace(datos_solicitud(), **cambio)


@pytest.mark.parametrize("aprobacion", [True, False])
def test_evaluacion_produce_evento_final_autosuficiente(aprobacion: bool) -> None:
    solicitud = solicitud_nueva(aprobacion)
    evaluacion = resultado(aprobacion)
    solicitud.retirar_eventos()
    solicitud.aplicar_evaluacion(
        evaluacion, id_evento=UUID(int=12), instante=INSTANTE + timedelta(seconds=2)
    )
    assert solicitud.version == 2
    assert solicitud.evaluacion == evaluacion
    assert len(solicitud.eventos_pendientes) == 1
    evento = solicitud.eventos_pendientes[0]
    clase = SolicitudPartnerListaParaAtencion if aprobacion else SolicitudPartnerRechazada
    assert isinstance(evento, clase)
    assert evento.id_solicitud == solicitud.id
    assert evento.datos == solicitud.datos
    assert evento.creada_en == INSTANTE
    assert evento.evaluacion == evaluacion
    assert evento.version_solicitud == 2
    assert evento.instante == solicitud.actualizada_en
    assert evento.estado is solicitud.estado
    if aprobacion:
        assert solicitud.estado is EstadoSolicitud.LISTA_PARA_ATENCION
        assert evaluacion.tipo_red is TipoRedProveedores.GENERAL_HDA
    else:
        assert solicitud.estado is EstadoSolicitud.RECHAZADA
        assert evaluacion.motivo is MotivoRechazo.APROBACION_PREVIA_REQUERIDA
        assert not any(
            isinstance(pendiente, SolicitudPartnerListaParaAtencion)
            for pendiente in solicitud.eventos_pendientes
        )


@pytest.mark.parametrize("aprobacion", [True, False])
def test_reentrega_equivalente_no_cambia_estado_version_fecha_ni_eventos(aprobacion: bool) -> None:
    solicitud = solicitud_nueva(aprobacion)
    evaluacion = resultado(aprobacion)
    solicitud.aplicar_evaluacion(
        evaluacion, id_evento=UUID(int=12), instante=INSTANTE + timedelta(seconds=2)
    )
    solicitud.retirar_eventos()
    fecha = solicitud.actualizada_en
    solicitud.aplicar_evaluacion(
        replace(evaluacion), id_evento=UUID(int=99), instante=INSTANTE + timedelta(days=1)
    )
    assert solicitud.eventos_pendientes == ()
    assert solicitud.version == 2
    assert solicitud.actualizada_en == fecha


@pytest.mark.parametrize(
    "cambio",
    [{"id_solicitud": UUID(int=99)}, {"id_partner": UUID(int=99)}, {"version_solicitud": 2}],
)
def test_evaluacion_ajena_o_desactualizada_no_modifica_agregado(cambio: dict[str, Any]) -> None:
    solicitud = solicitud_nueva()
    eventos = solicitud.eventos_pendientes
    with pytest.raises(ValueError):
        solicitud.aplicar_evaluacion(
            replace(resultado(), **cambio),
            id_evento=UUID(int=12),
            instante=INSTANTE + timedelta(seconds=2),
        )
    assert solicitud.estado is EstadoSolicitud.RECIBIDA
    assert solicitud.version == 1
    assert solicitud.evaluacion is None
    assert solicitud.eventos_pendientes == eventos


@pytest.mark.parametrize("aprobacion", [True, False])
@pytest.mark.parametrize("contradictoria", [True, False])
def test_no_sustituye_evaluacion_ni_revierte_estado_terminal(
    aprobacion: bool, contradictoria: bool
) -> None:
    solicitud = solicitud_nueva(aprobacion)
    inicial = resultado(aprobacion)
    solicitud.aplicar_evaluacion(
        inicial, id_evento=UUID(int=12), instante=INSTANTE + timedelta(seconds=2)
    )
    alternativa = (
        resultado(not aprobacion)
        if contradictoria
        else replace(inicial, id_evaluacion=UUID(int=90))
    )
    eventos = solicitud.eventos_pendientes
    with pytest.raises(ValueError):
        solicitud.aplicar_evaluacion(
            alternativa, id_evento=UUID(int=13), instante=INSTANTE + timedelta(seconds=3)
        )
    assert solicitud.evaluacion == inicial
    assert solicitud.version == 2
    assert solicitud.eventos_pendientes == eventos


@pytest.mark.parametrize(
    "cambio",
    [
        {"tipo_red": None},
        {"motivo": MotivoRechazo.APROBACION_PREVIA_REQUERIDA},
        {"resultado": ResultadoEvaluacion.NO_ADMISIBLE},
        {"version_politica": 0},
    ],
)
def test_contrato_no_admite_resultados_incoherentes(cambio: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        replace(resultado(), **cambio)


@pytest.mark.parametrize("aprobacion", [None, True, False])
def test_reconstruccion_conserva_estado_sin_reemitir_eventos(aprobacion: bool | None) -> None:
    solicitud = solicitud_nueva(aprobacion is not False)
    if aprobacion is not None:
        solicitud.aplicar_evaluacion(
            resultado(aprobacion), id_evento=UUID(int=12), instante=INSTANTE + timedelta(seconds=2)
        )
    copia = SolicitudPartner.reconstruir(
        id=solicitud.id,
        datos=solicitud.datos,
        creada_en=solicitud.creada_en,
        actualizada_en=solicitud.actualizada_en,
        estado=solicitud.estado,
        version=solicitud.version,
        evaluacion=solicitud.evaluacion,
    )
    assert copia == solicitud
    assert copia.datos == solicitud.datos
    assert copia.estado == solicitud.estado
    assert copia.version == solicitud.version
    assert copia.evaluacion == solicitud.evaluacion
    assert copia.eventos_pendientes == ()


@pytest.mark.parametrize(
    "cambio", [{"estado": EstadoSolicitud.RECHAZADA}, {"version": 2}, {"evaluacion": "invalida"}]
)
def test_reconstruccion_rechaza_estado_incoherente(cambio: dict[str, Any]) -> None:
    solicitud = solicitud_nueva()
    with pytest.raises(ValueError):
        replace(solicitud, **cambio)


def test_eventos_no_se_comparten_y_retirarlos_no_muta_copias() -> None:
    primera = solicitud_nueva()
    segunda = solicitud_nueva()
    copia = primera.eventos_pendientes
    retirados = primera.retirar_eventos()
    assert retirados == copia
    assert len(copia) == 1
    assert primera.eventos_pendientes == ()
    assert len(segunda.eventos_pendientes) == 1
    assert primera.retirar_eventos() == ()


def test_error_al_crear_evento_final_no_aplica_transicion_parcial() -> None:
    solicitud = solicitud_nueva()
    anteriores = solicitud.eventos_pendientes
    with pytest.raises(ValueError):
        solicitud.aplicar_evaluacion(
            resultado(), id_evento=UUID(int=12), instante=INSTANTE - timedelta(seconds=1)
        )
    assert solicitud.version == 1
    assert solicitud.evaluacion is None
    assert solicitud.eventos_pendientes == anteriores


@pytest.mark.parametrize(
    "cambio",
    [
        {"tipo_red": TipoRedProveedores.GENERAL_HDA},
        {"motivo": None},
        {"motivo": "DESCONOCIDO"},
        {"resultado": "NO_ADMISIBLE"},
        {"version_solicitud": True},
        {"instante": INSTANTE.replace(tzinfo=None)},
    ],
)
def test_contrato_de_rechazo_exige_motivo_valido_sin_red(cambio: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        replace(resultado(False), **cambio)


@pytest.mark.parametrize("aprobacion", [True, False])
def test_reconstruir_estado_terminal_con_resultado_opuesto_falla(aprobacion: bool) -> None:
    solicitud = solicitud_nueva(aprobacion)
    solicitud.aplicar_evaluacion(
        resultado(aprobacion), id_evento=UUID(int=12), instante=INSTANTE + timedelta(seconds=2)
    )
    with pytest.raises(ValueError):
        replace(solicitud, evaluacion=resultado(not aprobacion))
    with pytest.raises(ValueError):
        replace(solicitud, version=1)


def test_solicitud_vuelve_a_validar_contrato_antes_de_modificar_estado() -> None:
    solicitud = solicitud_nueva()
    evaluacion = resultado()
    object.__setattr__(evaluacion, "tipo_red", None)
    eventos = solicitud.eventos_pendientes
    with pytest.raises(ValueError):
        solicitud.aplicar_evaluacion(
            evaluacion, id_evento=UUID(int=12), instante=INSTANTE + timedelta(seconds=2)
        )
    assert solicitud.estado is EstadoSolicitud.RECIBIDA
    assert solicitud.evaluacion is None
    assert solicitud.eventos_pendientes == eventos


def test_evento_final_con_identidad_invalida_no_modifica_estado() -> None:
    solicitud = solicitud_nueva()
    eventos = solicitud.eventos_pendientes
    with pytest.raises(ValueError):
        solicitud.aplicar_evaluacion(
            resultado(), id_evento=UUID(int=0), instante=INSTANTE + timedelta(seconds=2)
        )
    assert solicitud.estado is EstadoSolicitud.RECIBIDA
    assert solicitud.version == 1
    assert solicitud.evaluacion is None
    assert solicitud.eventos_pendientes == eventos
