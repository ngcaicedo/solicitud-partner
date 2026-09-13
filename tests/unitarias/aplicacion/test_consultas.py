from unittest.mock import Mock

import pytest

from solicitudes_partner.modulos.solicitudes.aplicacion.consultas import RepositorioLectura
from solicitudes_partner.modulos.solicitudes.aplicacion.handlers.consultar_solicitudes import (
    ConsultarSolicitudHandler,
    ListarSolicitudesHandler,
)
from tests.unitarias.dominio.datos import ID_PARTNER, ID_SOLICITUD


def test_queries_solo_delegan_en_repositorio_de_lectura() -> None:
    repositorio = Mock(spec=RepositorioLectura)
    repositorio.obtener.return_value = None
    repositorio.listar.return_value = []
    assert ConsultarSolicitudHandler(repositorio)(ID_PARTNER, ID_SOLICITUD) is None
    assert ListarSolicitudesHandler(repositorio)(ID_PARTNER, 2, 4) == []
    repositorio.obtener.assert_called_once_with(ID_PARTNER, ID_SOLICITUD)
    repositorio.listar.assert_called_once_with(ID_PARTNER, 2, 4)
    with pytest.raises(ValueError):
        ListarSolicitudesHandler(repositorio)(ID_PARTNER, 101, 0)
    assert repositorio.listar.call_count == 1
