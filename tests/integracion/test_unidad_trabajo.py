from functools import partial
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

from solicitudes_partner.config.database import Database
from solicitudes_partner.config.persistencia import crear_uow_reglas, crear_uow_solicitudes
from solicitudes_partner.modulos.reglas_partner.dominio.eventos import ReglasDePartnerEvaluadas
from solicitudes_partner.modulos.reglas_partner.infraestructura.orm import EvaluacionSQL, OrigenSQL
from solicitudes_partner.modulos.reglas_partner.infraestructura.repositorios import (
    RepositorioEvaluacionesSQL,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.comandos import RegistrarSolicitudPartner
from solicitudes_partner.modulos.solicitudes.dominio.eventos import SolicitudPartnerRegistrada
from solicitudes_partner.modulos.solicitudes.infraestructura.repositorios import (
    RepositorioSolicitudesSQL,
)
from solicitudes_partner.seedwork.infraestructura.inbox import EntradaSQL
from solicitudes_partner.seedwork.infraestructura.outbox import SalidaSQL
from solicitudes_partner.seedwork.infraestructura.unidad_trabajo_sqlalchemy import UnidadTrabajoSQL
from tests.integracion.datos import flujo_sql
from tests.integracion.test_flujo_sql import evento_guardado
from tests.unitarias.dominio.datos import datos_solicitud, politica, registro


@pytest.mark.parametrize("etapa", ["evaluar", "aplicar"])
@pytest.mark.parametrize("fallo", ["inbox", "negocio", "outbox", "commit"])
def test_fallo_revierte_paso_completo(base: Database, etapa: str, fallo: str) -> None:
    with crear_uow_reglas(base) as unidad:
        unidad.politicas.guardar(politica())
        unidad.confirmar()
    flujo = flujo_sql(base)
    confirmacion = flujo.registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
    origen = evento_guardado(base, "SolicitudPartnerRegistrada")
    assert isinstance(origen, SolicitudPartnerRegistrada)
    if etapa == "aplicar":
        flujo.evaluar(origen)
        evento = evento_guardado(base, "ReglasDePartnerEvaluadas")
        assert isinstance(evento, ReglasDePartnerEvaluadas)
        operacion = partial(flujo.aplicar, evento)
    else:
        operacion = partial(flujo.evaluar, origen)
    repositorio = RepositorioEvaluacionesSQL if etapa == "evaluar" else RepositorioSolicitudesSQL
    clase, metodo = {
        "inbox": (UnidadTrabajoSQL, "preparar_entrada"),
        "negocio": (repositorio, "guardar"),
        "outbox": (UnidadTrabajoSQL, "registrar_salida"),
        "commit": (Session, "commit"),
    }[fallo]
    original = getattr(clase, metodo)

    def fallar(*argumentos: Any, **opciones: Any) -> None:
        if fallo != "commit":
            original(*argumentos, **opciones)
        raise RuntimeError("Fallo inyectado")

    with patch.object(clase, metodo, fallar), pytest.raises(RuntimeError, match="inyectado"):
        operacion()
    with base.session_factory() as sesion:
        assert sesion.scalar(select(func.count()).select_from(EntradaSQL)) == (
            0 if etapa == "evaluar" else 1
        )
        assert sesion.scalar(select(func.count()).select_from(SalidaSQL)) == (
            1 if etapa == "evaluar" else 2
        )
        assert sesion.scalar(select(func.count()).select_from(EvaluacionSQL)) == (
            0 if etapa == "evaluar" else 1
        )
        assert sesion.scalar(select(func.count()).select_from(OrigenSQL)) == (
            0 if etapa == "evaluar" else 1
        )
    with crear_uow_solicitudes(base) as unidad_solicitudes:
        solicitud = unidad_solicitudes.solicitudes.obtener(confirmacion.id_solicitud)
        assert solicitud is not None and solicitud.version == 1
    operacion()


def test_inbox_por_consumidor_y_rollback(base: Database) -> None:
    with crear_uow_reglas(base) as unidad:
        assert unidad.preparar_entrada("primero", registro())
    with crear_uow_reglas(base) as unidad:
        assert unidad.preparar_entrada("primero", registro())
        assert unidad.preparar_entrada("segundo", registro())
        unidad.confirmar()
    with crear_uow_reglas(base) as unidad:
        assert not unidad.preparar_entrada("primero", registro())


def test_entrada_nueva_sin_cambios_se_confirma(base: Database) -> None:
    with crear_uow_reglas(base) as unidad:
        unidad.politicas.guardar(politica())
        unidad.confirmar()
    flujo = flujo_sql(base)
    flujo.evaluar(registro())
    with base.engine.begin() as conexion:
        conexion.execute(delete(EntradaSQL))
    flujo.evaluar(registro())
    with base.session_factory() as sesion:
        assert sesion.scalar(select(func.count()).select_from(EntradaSQL)) == 1
        assert sesion.scalar(select(func.count()).select_from(SalidaSQL)) == 1


def test_sesiones_distintas_y_cierre(base: Database) -> None:
    primera = crear_uow_solicitudes(base)
    segunda = crear_uow_solicitudes(base)
    with primera, segunda:
        assert primera.sesion is not segunda.sesion
        assert primera.sesion.scalar(select(func.pg_backend_pid())) != segunda.sesion.scalar(
            select(func.pg_backend_pid())
        )
    with pytest.raises(RuntimeError, match="inactiva"):
        assert primera.sesion is not None
    assert isinstance(base.engine.pool, QueuePool)
    assert base.engine.pool.checkedout() == 0


def test_payload_invalido_revierte_registro(base: Database) -> None:
    from solicitudes_partner.modulos.solicitudes.infraestructura.orm import SolicitudSQL
    from tests.unitarias.dominio.datos import solicitud_nueva

    with pytest.raises(ValueError), crear_uow_solicitudes(base) as unidad:
        solicitud = solicitud_nueva()
        unidad.solicitudes.guardar(solicitud)
        evento = solicitud.retirar_eventos()[0]
        object.__setattr__(evento, "version_solicitud", 99)
        unidad.registrar_salida(evento)
        unidad.confirmar()
    with base.session_factory() as sesion:
        assert sesion.scalar(select(func.count()).select_from(SolicitudSQL)) == 0
        assert sesion.scalar(select(func.count()).select_from(SalidaSQL)) == 0


def test_commit_fallido_no_devuelve_confirmacion(base: Database) -> None:
    from solicitudes_partner.modulos.solicitudes.infraestructura.orm import SolicitudSQL

    flujo = flujo_sql(base)
    with patch.object(Session, "commit", side_effect=RuntimeError("Commit fallido")):
        with pytest.raises(RuntimeError, match="Commit fallido"):
            flujo.registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
    with base.session_factory() as sesion:
        assert sesion.scalar(select(func.count()).select_from(SolicitudSQL)) == 0
        assert sesion.scalar(select(func.count()).select_from(SalidaSQL)) == 0
