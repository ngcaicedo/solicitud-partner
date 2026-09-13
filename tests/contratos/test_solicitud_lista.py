import json
from datetime import timedelta
from uuid import UUID

import pytest
from pulsar.schema import AvroSchema

from solicitudes_partner.modulos.solicitudes.infraestructura.esquemas.v1.eventos import (
    SolicitudListaV1,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.mapeadores_eventos import (
    evento_integracion,
)
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio
from tests.unitarias.dominio.datos import INSTANTE, solicitud_nueva
from tests.unitarias.dominio.datos_resultados import resultado_solicitud


def terminal(aprobacion: bool = True) -> EventoDominio:
    solicitud = solicitud_nueva(aprobacion)
    solicitud.retirar_eventos()
    solicitud.aplicar_resultado_evaluacion(
        resultado_solicitud(aprobacion),
        id_evento=UUID(int=15),
        instante=INSTANTE + timedelta(seconds=2),
    )
    return solicitud.retirar_eventos()[0]


def test_contrato_avro_conserva_identidad_y_datos() -> None:
    evento = terminal()
    mensaje = evento_integracion(evento)
    esquema = AvroSchema(SolicitudListaV1)
    decodificado = esquema.decode(esquema.encode(mensaje))
    assert decodificado.event_id == str(evento.id_evento)
    assert decodificado.tipo == "SolicitudDePartnerListaParaAtencion.v1"
    assert decodificado.id_solicitud == str(UUID(int=1))
    assert decodificado.correlacion == str(UUID(int=1))
    assert decodificado.tipo_red == "GENERAL_HDA"
    assert esquema.encode(mensaje) == esquema.encode(evento_integracion(evento))
    assert "id_solicitud" in json.dumps(SolicitudListaV1.schema())


def test_rechazo_no_se_convierte_en_solicitud_lista() -> None:
    with pytest.raises(ValueError, match="lista"):
        evento_integracion(terminal(False))


def test_archivos_publicos_corresponden_al_contrato() -> None:
    import io
    from pathlib import Path

    import fastavro

    carpeta = Path(__file__).resolve().parents[2] / "docs/contratos"
    esquema = json.loads((carpeta / "solicitud-lista-v1.avsc").read_text())
    ejemplo = json.loads((carpeta / "solicitud-lista-v1.ejemplo.json").read_text())
    assert esquema == SolicitudListaV1.schema()
    assert set(ejemplo) == {campo["name"] for campo in esquema["fields"]}
    datos = AvroSchema(SolicitudListaV1).encode(evento_integracion(terminal()))
    assert fastavro.schemaless_reader(io.BytesIO(datos), esquema) == ejemplo


@pytest.mark.parametrize("red", ["GENERAL_HDA", "HOMOLOGADA_PARTNER"])
def test_instalacion_sin_aprobacion_conserva_red(red: str) -> None:
    from dataclasses import replace

    from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
        TipoRedProveedores,
        TipoSolicitud,
    )

    solicitud = solicitud_nueva(None, TipoSolicitud.INSTALACION)
    solicitud.retirar_eventos()
    solicitud.aplicar_resultado_evaluacion(
        replace(resultado_solicitud(), tipo_red=TipoRedProveedores(red)),
        id_evento=UUID(int=15),
        instante=INSTANTE + timedelta(seconds=2),
    )
    esquema = AvroSchema(SolicitudListaV1)
    mensaje = esquema.decode(esquema.encode(evento_integracion(solicitud.retirar_eventos()[0])))
    assert mensaje.tipo_red == red
    assert mensaje.tipo_solicitud == "INSTALACION"
    assert mensaje.aprobacion_previa is None
