from unittest.mock import Mock
from uuid import uuid4

import pytest

from solicitudes_partner.config.rutas import destinos_evento
from solicitudes_partner.config.serializacion import decodificar_evento, serializar_evento
from solicitudes_partner.modulos.solicitudes.dominio.eventos import SolicitudPartnerRegistrada
from solicitudes_partner.seedwork.aplicacion.publicacion import Publicacion
from solicitudes_partner.seedwork.infraestructura.bus_eventos_local import BusEventosLocal
from solicitudes_partner.seedwork.infraestructura.publicador_bus import PublicadorBus
from tests.unitarias.dominio.datos import registro, resultado


def test_entrega_durable_ejecuta_solo_destinatario_y_no_encola() -> None:
    bus = BusEventosLocal()
    destinatario = Mock()
    ajeno = Mock()
    bus.suscribir(SolicitudPartnerRegistrada, "reglas_partner.evaluar", destinatario)
    bus.suscribir(SolicitudPartnerRegistrada, "otro", ajeno)
    evento = registro()
    publicacion = Publicacion(
        uuid4(), evento.id_evento, "reglas_partner.evaluar", serializar_evento(evento)
    )
    assert PublicadorBus(bus, decodificar_evento).publicar(publicacion)
    destinatario.assert_called_once_with(evento)
    ajeno.assert_not_called()
    assert not bus.pendientes and not bus.publicados


def test_entrega_sin_suscriptor_o_con_error_no_se_confirma() -> None:
    bus = BusEventosLocal()
    evento = registro()
    publicacion = Publicacion(
        uuid4(), evento.id_evento, "reglas_partner.evaluar", serializar_evento(evento)
    )
    publicador = PublicadorBus(bus, decodificar_evento)
    with pytest.raises(ValueError, match="suscriptor"):
        publicador.publicar(publicacion)
    bus.suscribir(
        SolicitudPartnerRegistrada,
        "reglas_partner.evaluar",
        Mock(side_effect=RuntimeError("fallo")),
    )
    with pytest.raises(RuntimeError, match="fallo"):
        publicador.publicar(publicacion)
    assert not bus.pendientes


def test_rutas_internas_no_son_topicos() -> None:
    assert destinos_evento(registro()) == ("reglas_partner.evaluar", "cqrs.solicitud.v1")
    assert destinos_evento(resultado()) == ("solicitudes.aplicar",)
