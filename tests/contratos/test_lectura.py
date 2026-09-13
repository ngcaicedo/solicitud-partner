from datetime import timedelta
from uuid import uuid4

import pytest
from pulsar.schema import AvroSchema

from solicitudes_partner.config.rutas import DESTINOS_CQRS, destinos_evento
from solicitudes_partner.config.serializacion import serializar_evento
from solicitudes_partner.modulos.solicitudes.infraestructura.esquemas.v1.lectura import (
    SolicitudLecturaV1,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.mapeadores import (
    actualizacion_desde_evento,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.mapeadores_eventos import (
    leer_mensaje,
    mensaje_lectura,
)
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio
from tests.unitarias.dominio.datos import INSTANTE, registro, resultado, solicitud_nueva
from tests.unitarias.dominio.datos_resultados import resultado_solicitud


@pytest.mark.parametrize("estado", ["recibida", "lista", "rechazada"])
def test_avro_cqrs_conserva_estado_nulos_e_identidad(estado: str) -> None:
    evento: EventoDominio
    if estado == "recibida":
        evento = registro()
    else:
        solicitud = solicitud_nueva(estado == "lista")
        solicitud.retirar_eventos()
        solicitud.aplicar_resultado_evaluacion(
            resultado_solicitud(estado == "lista"),
            id_evento=uuid4(),
            instante=INSTANTE + timedelta(seconds=2),
        )
        evento = solicitud.retirar_eventos()[0]
    documento = serializar_evento(evento)
    mensaje = mensaje_lectura(documento)
    esquema = AvroSchema(SolicitudLecturaV1)
    assert leer_mensaje(esquema.decode(esquema.encode(mensaje))) == actualizacion_desde_evento(
        evento
    )
    assert mensaje_lectura(documento).event_id == mensaje.event_id
    assert DESTINOS_CQRS[0] in destinos_evento(evento)
    if estado != "lista":
        assert mensaje.tipo_red is None
        assert "integracion.solicitud_lista.v1" not in destinos_evento(evento)
    if estado == "recibida":
        assert mensaje.resultado is mensaje.id_politica is mensaje.version_politica is None


def test_cqrs_no_publica_evento_de_reglas() -> None:
    assert not set(destinos_evento(resultado())) & set(DESTINOS_CQRS)
    with pytest.raises(ValueError):
        mensaje_lectura(serializar_evento(resultado()))


def test_contrato_desconocido_o_estado_incoherente_no_se_proyecta() -> None:
    mensaje = mensaje_lectura(serializar_evento(registro()))
    mensaje.version_contrato = 2
    with pytest.raises(ValueError):
        leer_mensaje(mensaje)
    mensaje.version_contrato = 1
    mensaje.estado = "RECHAZADA"
    with pytest.raises(ValueError):
        leer_mensaje(mensaje)


def test_archivos_de_lectura_corresponden_al_contrato() -> None:
    import io
    import json
    from pathlib import Path

    import fastavro

    carpeta = Path(__file__).resolve().parents[2] / "docs/contratos"
    esquema = json.loads((carpeta / "solicitud-lectura-v1.avsc").read_text())
    ejemplo = json.loads((carpeta / "solicitud-lectura-v1.ejemplo.json").read_text())
    assert esquema == SolicitudLecturaV1.schema()
    mensaje = mensaje_lectura(serializar_evento(registro()))
    contenido = AvroSchema(SolicitudLecturaV1).encode(mensaje)
    assert fastavro.schemaless_reader(io.BytesIO(contenido), esquema) == ejemplo
