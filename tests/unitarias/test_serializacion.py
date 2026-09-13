import json
from dataclasses import replace
from datetime import timedelta
from uuid import UUID

import pytest

from solicitudes_partner.config.serializacion import decodificar_evento, serializar_evento
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio
from tests.unitarias.dominio.datos import INSTANTE, registro, resultado, solicitud_nueva
from tests.unitarias.dominio.datos_resultados import resultado_solicitud


def eventos() -> list[EventoDominio]:
    salidas: list[EventoDominio] = [registro(), resultado()]
    for aprobacion in (True, False):
        solicitud = solicitud_nueva(aprobacion)
        solicitud.retirar_eventos()
        solicitud.aplicar_resultado_evaluacion(
            resultado_solicitud(aprobacion),
            id_evento=UUID(int=20),
            instante=INSTANTE + timedelta(seconds=2),
        )
        salidas.extend(solicitud.retirar_eventos())
    return salidas


@pytest.mark.parametrize("evento", eventos())
def test_eventos_sobreviven_json_con_identidad_y_tipos(evento: EventoDominio) -> None:
    documento = json.loads(json.dumps(serializar_evento(evento)))
    assert decodificar_evento(documento) == evento
    assert documento["version_formato"] == 1


@pytest.mark.parametrize("campo,valor", [("version_formato", 99), ("tipo", "Desconocido")])
def test_formato_desconocido_falla(campo: str, valor: object) -> None:
    documento = serializar_evento(registro())
    documento[campo] = valor
    with pytest.raises(ValueError):
        decodificar_evento(documento)


def test_serializacion_rechaza_evento_mutado_invalido() -> None:
    evento = replace(registro())
    object.__setattr__(evento, "version_solicitud", 3)
    with pytest.raises(ValueError):
        serializar_evento(evento)


def test_instantes_equivalentes_tienen_representacion_estable() -> None:
    from datetime import timezone

    original = registro()
    equivalente = replace(
        original, instante=original.instante.astimezone(timezone(timedelta(hours=-5)))
    )
    assert original == equivalente
    assert serializar_evento(original) == serializar_evento(equivalente)
