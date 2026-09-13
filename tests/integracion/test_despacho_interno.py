from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import func, select, update

from solicitudes_partner.config.bootstrap import componer_despacho_interno
from solicitudes_partner.config.database import Database
from solicitudes_partner.config.persistencia import crear_uow_reglas, crear_uow_solicitudes
from solicitudes_partner.modulos.solicitudes.aplicacion.comandos import RegistrarSolicitudPartner
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import EstadoSolicitud
from solicitudes_partner.seedwork.infraestructura.outbox import (
    EventoSQL,
    RepositorioOutbox,
    SalidaSQL,
)
from tests.integracion.datos import flujo_sql
from tests.unitarias.dominio.datos import datos_solicitud, politica


@pytest.mark.parametrize("aprobacion", [True, False])
def test_flujo_interno_archiva_sin_depender_del_broker(base: Database, aprobacion: bool) -> None:
    with crear_uow_reglas(base) as unidad:
        unidad.politicas.guardar(politica())
        unidad.confirmar()
    confirmacion = flujo_sql(base).registrar(
        RegistrarSolicitudPartner(datos=datos_solicitud(aprobacion))
    )
    despacho = componer_despacho_interno(base)
    assert despacho.despachar_lote(1) == 1
    assert despacho.despachar_lote(1) == 1
    assert despacho.despachar_lote(1) == 0
    with crear_uow_solicitudes(base) as unidad:
        solicitud = unidad.solicitudes.obtener(confirmacion.id_solicitud)
        assert solicitud is not None
        assert solicitud.estado == (
            EstadoSolicitud.LISTA_PARA_ATENCION if aprobacion else EstadoSolicitud.RECHAZADA
        )
    with base.session_factory() as sesion:
        assert sesion.scalar(select(func.count()).select_from(EventoSQL)) == 3
    assert RepositorioOutbox(base.session_factory).metricas()["pendientes"] == 2 + int(aprobacion)


def test_reinicio_tras_commit_antes_de_marcar_no_repite_efecto(base: Database) -> None:
    with crear_uow_reglas(base) as unidad:
        unidad.politicas.guardar(politica())
        unidad.confirmar()
    flujo_sql(base).registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
    despacho = componer_despacho_interno(base)
    with patch.object(despacho.outbox, "confirmar", side_effect=RuntimeError("caida")):
        with pytest.raises(RuntimeError, match="caida"):
            despacho.despachar_lote(1)
    with base.engine.begin() as conexion:
        conexion.execute(
            update(SalidaSQL).values(vence_en=func.clock_timestamp() - timedelta(seconds=1))
        )
    reiniciado = componer_despacho_interno(base)
    reiniciado.despachar_lote(1)
    reiniciado.despachar_lote(1)
    with base.session_factory() as sesion:
        assert sesion.scalar(select(func.count()).select_from(EventoSQL)) == 3


def test_fallo_sin_handler_conserva_pendiente(base: Database) -> None:
    from solicitudes_partner.config.serializacion import decodificar_evento
    from solicitudes_partner.seedwork.infraestructura.bus_eventos_local import BusEventosLocal
    from solicitudes_partner.seedwork.infraestructura.despacho_outbox import DespachadorOutbox
    from solicitudes_partner.seedwork.infraestructura.publicador_bus import PublicadorBus

    flujo_sql(base).registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
    outbox = RepositorioOutbox(base.session_factory, ("reglas_partner.evaluar",))
    despacho = DespachadorOutbox(
        outbox, PublicadorBus(BusEventosLocal(), decodificar_evento), "prueba"
    )
    assert despacho.despachar_lote(1) == 0
    assert outbox.metricas()["pendientes"] == 2
    assert any("suscriptor" in (salida["ultimo_error"] or "") for salida in outbox.inspeccionar())


def test_archivo_revierte_con_la_unidad_de_trabajo(base: Database) -> None:
    from tests.unitarias.dominio.datos import registro

    with crear_uow_solicitudes(base) as unidad:
        unidad.registrar_salida(registro())
    with base.session_factory() as sesion:
        assert sesion.scalar(select(func.count()).select_from(EventoSQL)) == 0
        assert sesion.scalar(select(func.count()).select_from(SalidaSQL)) == 0


def test_documento_invalido_no_se_confirma(base: Database) -> None:
    flujo_sql(base).registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
    with base.engine.begin() as conexion:
        conexion.execute(update(SalidaSQL).values(documento={"tipo": "desconocido"}))
    despacho = componer_despacho_interno(base)
    assert despacho.despachar_lote(1) == 0
    assert despacho.outbox.metricas()["pendientes"] == 2
    assert any(salida["ultimo_error"] for salida in despacho.outbox.inspeccionar())
