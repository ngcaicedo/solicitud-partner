from collections.abc import Iterator
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from solicitudes_partner.api.app import create_app
from solicitudes_partner.api.solicitudes import obtener_consulta, obtener_listado, obtener_registro
from solicitudes_partner.config.settings import Settings
from solicitudes_partner.modulos.solicitudes.aplicacion.confirmaciones import (
    ConfirmacionRegistroSolicitud,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.excepciones import ConflictoRegistro
from tests.unitarias.dominio.datos import ID_PARTNER, ID_SOLICITUD


@pytest.fixture
def api() -> Iterator[tuple[TestClient, Mock, Mock, Mock]]:
    registro = Mock(return_value=ConfirmacionRegistroSolicitud(id_solicitud=ID_SOLICITUD))
    consulta = Mock(return_value=None)
    listado = Mock(return_value=[])
    app = create_app(Settings())
    app.dependency_overrides[obtener_registro] = lambda: registro
    app.dependency_overrides[obtener_consulta] = lambda: consulta
    app.dependency_overrides[obtener_listado] = lambda: listado
    with TestClient(app, headers={"X-Partner-Laboratorio": str(ID_PARTNER)}) as cliente:
        yield cliente, registro, consulta, listado


def test_post_confirma_y_consulta_ausente_no_lee_escritura(
    api: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    cliente, registro, consulta, _ = api
    payload = dict(
        referencia_externa="SIN-100",
        categoria="plomeria",
        tipo="SINIESTRO",
        aprobacion_previa=False,
    )
    respuesta = cliente.post("/solicitudes", json=payload)
    assert respuesta.status_code == 202
    assert respuesta.json() == {"id_solicitud": str(ID_SOLICITUD), "recepcion_confirmada": True}
    assert respuesta.headers["location"].endswith(f"/solicitudes/{ID_SOLICITUD}")
    assert registro.call_args.args[0].datos.id_partner == ID_PARTNER
    assert registro.call_args.args[0].datos.aprobacion_previa is False
    assert not consulta.called
    assert cliente.get(respuesta.headers["location"]).status_code == 404
    consulta.assert_called_once_with(ID_PARTNER, ID_SOLICITUD)
    assert registro.call_count == 1
    assert cliente.post("/solicitudes", json=payload).json() == respuesta.json()


@pytest.mark.parametrize(
    "cambios",
    [
        {"aprobacion_previa": None},
        {"aprobacion_previa": "false"},
        {"aprobacion_previa": 0},
        {"categoria": "   "},
        {"tipo": "otro"},
        {"id_partner": str(uuid4())},
    ],
)
def test_datos_invalidos_no_llegan_al_comando(
    api: tuple[TestClient, Mock, Mock, Mock], cambios: dict[str, object]
) -> None:
    cliente, registro, _, _ = api
    payload = dict(
        referencia_externa="SIN-100", categoria="plomeria", tipo="SINIESTRO", aprobacion_previa=True
    )
    assert cliente.post("/solicitudes", json=payload | cambios).status_code == 422
    registro.assert_not_called()


def test_siniestro_omitido_e_instalacion_sin_aprobacion(
    api: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    cliente, registro, _, _ = api
    payload = dict(referencia_externa="REF", categoria="plomeria", tipo="SINIESTRO")
    assert cliente.post("/solicitudes", json=payload).status_code == 422
    assert cliente.post("/solicitudes", json=payload | {"tipo": "INSTALACION"}).status_code == 202
    assert registro.call_args.args[0].datos.aprobacion_previa is None


def test_conflicto_y_paginacion(api: tuple[TestClient, Mock, Mock, Mock]) -> None:
    cliente, registro, _, listado = api
    registro.side_effect = ConflictoRegistro("conflicto")
    assert (
        cliente.post(
            "/solicitudes",
            json=dict(referencia_externa="REF", categoria="plomeria", tipo="INSTALACION"),
        ).status_code
        == 409
    )
    assert cliente.get("/solicitudes?limite=2&desplazamiento=4").json() == []
    listado.assert_called_once_with(ID_PARTNER, 2, 4)
    assert cliente.get("/solicitudes?limite=101").status_code == 422
    assert cliente.get("/solicitudes?desplazamiento=-1").status_code == 422


def test_sin_infraestructura_solo_health_funciona() -> None:
    with TestClient(create_app(Settings())) as cliente:
        assert cliente.get("/health/live").status_code == 200
        assert (
            cliente.get(
                "/solicitudes", headers={"X-Partner-Laboratorio": str(ID_PARTNER)}
            ).status_code
            == 503
        )


def test_fallo_persistencia_no_confirma_recepcion(api: tuple[TestClient, Mock, Mock, Mock]) -> None:
    from sqlalchemy.exc import OperationalError

    cliente, registro, _, _ = api
    registro.side_effect = OperationalError(None, None, Exception("base detenida"))
    respuesta = cliente.post(
        "/solicitudes",
        json=dict(referencia_externa="REF", categoria="plomeria", tipo="INSTALACION"),
    )
    assert respuesta.status_code == 503
    assert "id_solicitud" not in respuesta.json()
    assert "Location" not in respuesta.headers
