from dataclasses import replace
from datetime import datetime
from typing import cast
from uuid import UUID

import pytest

from solicitudes_partner.seedwork.dominio.entidades import Entidad
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio

from .datos import INSTANTE, datos_solicitud, solicitud_nueva


def test_entidades_comparan_identidad_y_objetos_valor_comparan_atributos() -> None:
    primera = solicitud_nueva()
    segunda = replace(primera, datos=replace(primera.datos, categoria="electricidad"))
    assert primera == segunda
    assert hash(primera) == hash(segunda)
    assert primera != replace(primera, id=UUID(int=99))
    assert primera != Entidad(id=primera.id)
    assert datos_solicitud() == datos_solicitud()
    assert datos_solicitud() != replace(datos_solicitud(), categoria="electricidad")


@pytest.mark.parametrize("identificador", ["", 123, UUID(int=0)])
def test_identidad_invalida_se_rechaza(identificador: object) -> None:
    with pytest.raises(ValueError):
        replace(solicitud_nueva(), id=cast(UUID, identificador))


def test_evento_exige_fecha_con_zona_horaria() -> None:
    with pytest.raises(ValueError):
        EventoDominio(id_evento=UUID(int=90), instante=datetime(2026, 9, 12))
    assert EventoDominio(id_evento=UUID(int=90), instante=INSTANTE).instante == INSTANTE
