from threading import Event
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from solicitudes_partner.api.app import create_app
from solicitudes_partner.config.database import Database
from solicitudes_partner.config.settings import Settings
from solicitudes_partner.seedwork.infraestructura.ciclos import Procesamiento, iniciar_ciclo


def test_suscripcion_precede_publicacion_sin_bloquear_http_y_cierra_recursos() -> None:
    base = Mock(spec=Database)
    consumidor = Mock()
    interno = Mock(propietario="interno")
    externo = Mock(propietario="externo")
    cqrs = Mock()
    cerrar_externo = Mock()
    cerrar_cqrs = Mock()
    abrir_iniciado = Event()
    permitir_suscripcion = Event()
    publicado = Event()
    procesamientos: list[Procesamiento] = []

    def abrir() -> None:
        if consumidor.abrir.call_count == 1:
            raise RuntimeError("broker temporalmente ausente")
        abrir_iniciado.set()
        if not permitir_suscripcion.wait(2):
            raise RuntimeError("broker temporalmente ausente")

    def publicar(limite: int) -> None:
        assert permitir_suscripcion.is_set()
        publicado.set()

    consumidor.abrir.side_effect = abrir
    cqrs.despachar_lote.side_effect = publicar

    def capturar_ciclo(*args: object, **kwargs: object) -> Procesamiento:
        from typing import Any, cast

        procesamiento = iniciar_ciclo(*cast(Any, args), **cast(Any, kwargs))
        procesamientos.append(procesamiento)
        return procesamiento

    def cerrar_base() -> None:
        assert all(not procesamiento.hilo.is_alive() for procesamiento in procesamientos)
        consumidor.cerrar.assert_called_once_with()
        cerrar_externo.assert_called_once_with()
        cerrar_cqrs.assert_called_once_with()

    base.close.side_effect = cerrar_base
    with (
        patch("solicitudes_partner.config.procesamiento.verificar_destinos"),
        patch(
            "solicitudes_partner.config.procesamiento.componer_despacho_interno",
            return_value=interno,
        ),
        patch(
            "solicitudes_partner.config.procesamiento.componer_publicacion",
            return_value=(externo, cerrar_externo),
        ),
        patch(
            "solicitudes_partner.config.procesamiento.componer_publicacion_cqrs",
            return_value=(cqrs, cerrar_cqrs),
        ),
        patch(
            "solicitudes_partner.config.procesamiento.componer_proyeccion", return_value=consumidor
        ),
        patch("solicitudes_partner.config.procesamiento.iniciar_ciclo", side_effect=capturar_ciclo),
    ):
        app = create_app(Settings(database_url="postgresql+psycopg://test"), lambda _: base)
        with TestClient(app) as cliente:
            try:
                assert abrir_iniciado.wait(1)
                assert cliente.get("/openapi.json").status_code == 200
                cqrs.despachar_lote.assert_not_called()
                assert interno.despachar_lote.called
                permitir_suscripcion.set()
                assert publicado.wait(2)
            finally:
                permitir_suscripcion.set()
    assert len(procesamientos) == 4
    base.close.assert_called_once_with()


def test_inicio_parcial_detiene_hilos_antes_de_cerrar_base() -> None:
    base = Mock(spec=Database)
    procesamiento = iniciar_ciclo(lambda: None, "prueba-inicio-parcial")

    def cerrar_base() -> None:
        assert not procesamiento.hilo.is_alive()

    base.close.side_effect = cerrar_base
    with (
        patch("solicitudes_partner.config.procesamiento.verificar_destinos"),
        patch("solicitudes_partner.config.procesamiento.componer_proyeccion"),
        patch(
            "solicitudes_partner.config.procesamiento.componer_publicacion_cqrs",
            return_value=(Mock(), Mock()),
        ),
        patch(
            "solicitudes_partner.config.procesamiento.iniciar_despacho_interno",
            return_value=procesamiento,
        ),
        patch(
            "solicitudes_partner.config.procesamiento.iniciar_publicacion",
            side_effect=RuntimeError("inicio interrumpido"),
        ),
    ):
        app = create_app(Settings(database_url="postgresql+psycopg://test"), lambda _: base)
        try:
            with pytest.raises(RuntimeError, match="inicio interrumpido"), TestClient(app):
                pass
            base.close.assert_called_once_with()
        finally:
            procesamiento.detener()
