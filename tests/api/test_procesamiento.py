from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from solicitudes_partner.api.app import create_app
from solicitudes_partner.config.database import Database
from solicitudes_partner.config.settings import Settings


@pytest.mark.parametrize("fallar", [False, True])
def test_lifespan_inicia_y_cierra_procesamiento_antes_de_base(fallar: bool) -> None:
    pasos: list[str] = []
    base = Mock(spec=Database)
    base.close.side_effect = lambda: pasos.append("cerrar_base")
    configuracion = Settings(database_url="postgresql+psycopg://test")

    @asynccontextmanager
    async def procesamiento(database: Database, settings: Settings) -> AsyncIterator[None]:
        assert database is base and settings is configuracion
        pasos.append("iniciar")
        try:
            yield
        finally:
            pasos.append("detener")

    app = create_app(configuracion, lambda _: base, processing_factory=procesamiento)
    try:
        with TestClient(app) as cliente:
            assert pasos == ["iniciar"]
            assert cliente.get("/health/live").status_code == 200
            if fallar:
                raise RuntimeError("fallo de peticion")
    except RuntimeError:
        assert fallar
    assert pasos == ["iniciar", "detener", "cerrar_base"]
    assert app.state.database is None


def test_fallo_al_iniciar_procesamiento_cierra_base() -> None:
    base = Mock(spec=Database)

    @asynccontextmanager
    async def procesamiento(database: Database, settings: Settings) -> AsyncIterator[None]:
        raise RuntimeError("fallo al iniciar")
        yield

    app = create_app(
        Settings(database_url="postgresql+psycopg://test"),
        lambda _: base,
        processing_factory=procesamiento,
    )
    with pytest.raises(RuntimeError, match="fallo al iniciar"), TestClient(app):
        pass
    base.close.assert_called_once_with()
    assert app.state.database is None
