from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from threading import Barrier, local
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlalchemy import func, select

from solicitudes_partner.config.database import Database
from solicitudes_partner.config.persistencia import crear_uow_reglas, crear_uow_solicitudes
from solicitudes_partner.modulos.reglas_partner.dominio.eventos import ReglasDePartnerEvaluadas
from solicitudes_partner.modulos.reglas_partner.infraestructura.orm import EvaluacionSQL
from solicitudes_partner.modulos.reglas_partner.infraestructura.repositorios import (
    RepositorioEvaluacionesSQL,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.comandos import RegistrarSolicitudPartner
from solicitudes_partner.modulos.solicitudes.aplicacion.excepciones import ConflictoRegistro
from solicitudes_partner.modulos.solicitudes.dominio.entidades import SolicitudPartner
from solicitudes_partner.modulos.solicitudes.dominio.eventos import SolicitudPartnerRegistrada
from solicitudes_partner.modulos.solicitudes.infraestructura.orm import SolicitudSQL
from solicitudes_partner.modulos.solicitudes.infraestructura.repositorios import (
    RepositorioSolicitudesSQL,
)
from solicitudes_partner.seedwork.aplicacion.excepciones import ColisionPersistencia
from solicitudes_partner.seedwork.infraestructura.outbox import SalidaSQL
from tests.integracion.datos import flujo_sql
from tests.integracion.test_flujo_sql import evento_guardado
from tests.unitarias.dominio.datos import (
    ID_SOLICITUD,
    INSTANTE,
    datos_solicitud,
    politica,
    solicitud_nueva,
)
from tests.unitarias.dominio.datos_resultados import resultado_solicitud


def test_registros_concurrentes_equivalentes(base: Database) -> None:
    barrera = Barrier(2)
    estado = local()
    original = RepositorioSolicitudesSQL.obtener_por_referencia

    def leer(
        repositorio: RepositorioSolicitudesSQL, id_partner: UUID, referencia: str
    ) -> SolicitudPartner | None:
        valor = original(repositorio, id_partner, referencia)
        if not getattr(estado, "esperado", False):
            estado.esperado = True
            barrera.wait(timeout=5)
        return valor

    flujo = flujo_sql(base)
    comando = RegistrarSolicitudPartner(datos=datos_solicitud())
    with patch.object(RepositorioSolicitudesSQL, "obtener_por_referencia", leer):
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            confirmaciones = list(ejecutor.map(flujo.registrar, [comando, comando]))
    assert confirmaciones[0] == confirmaciones[1]
    with base.session_factory() as sesion:
        assert sesion.scalar(select(func.count()).select_from(SolicitudSQL)) == 1
        assert sesion.scalar(select(func.count()).select_from(SalidaSQL)) == 1


@contextmanager
def sincronizar_lecturas(clase: type, metodo: str) -> Iterator[None]:
    barrera = Barrier(2)
    estado = local()
    original: Callable[..., Any] = getattr(clase, metodo)

    def leer(*argumentos: Any, **opciones: Any) -> Any:
        valor = original(*argumentos, **opciones)
        if not getattr(estado, "esperado", False):
            estado.esperado = True
            barrera.wait(timeout=5)
        return valor

    with patch.object(clase, metodo, leer):
        yield


def test_registros_concurrentes_conflictivos(base: Database) -> None:
    flujo = flujo_sql(base)
    comandos = [
        RegistrarSolicitudPartner(datos=datos_solicitud()),
        RegistrarSolicitudPartner(datos=replace(datos_solicitud(), categoria="otra")),
    ]
    with sincronizar_lecturas(RepositorioSolicitudesSQL, "obtener_por_referencia"):
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            futuros = [ejecutor.submit(flujo.registrar, comando) for comando in comandos]
            exitos = conflictos = 0
            for futuro in futuros:
                try:
                    futuro.result(timeout=10)
                    exitos += 1
                except ConflictoRegistro:
                    conflictos += 1
    assert exitos == conflictos == 1
    with base.session_factory() as sesion:
        assert sesion.scalar(select(func.count()).select_from(SalidaSQL)) == 1


def test_consumidores_concurrentes_no_duplican_efectos(base: Database) -> None:
    with crear_uow_reglas(base) as unidad:
        unidad.politicas.guardar(politica())
        unidad.confirmar()
    flujo = flujo_sql(base)
    flujo.registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
    registro = evento_guardado(base, "SolicitudPartnerRegistrada")
    assert isinstance(registro, SolicitudPartnerRegistrada)
    with sincronizar_lecturas(RepositorioEvaluacionesSQL, "obtener_por_solicitud"):
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            assert list(ejecutor.map(flujo.evaluar, [registro, registro])) == [None, None]
    evaluacion = evento_guardado(base, "ReglasDePartnerEvaluadas")
    assert isinstance(evaluacion, ReglasDePartnerEvaluadas)
    with sincronizar_lecturas(RepositorioSolicitudesSQL, "obtener"):
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            assert list(ejecutor.map(flujo.aplicar, [evaluacion, evaluacion])) == [None, None]
    with base.session_factory() as sesion:
        assert sesion.scalar(select(func.count()).select_from(EvaluacionSQL)) == 1
        assert sesion.scalar(select(func.count()).select_from(SalidaSQL)) == 3


def test_version_obsoleta_falla_sin_salida_del_perdedor(base: Database) -> None:
    with crear_uow_solicitudes(base) as unidad:
        unidad.solicitudes.guardar(solicitud_nueva())
        unidad.confirmar()
    with crear_uow_solicitudes(base) as primera:
        with pytest.raises(ColisionPersistencia), crear_uow_solicitudes(base) as segunda:
            anterior = primera.solicitudes.obtener(ID_SOLICITUD)
            obsoleta = segunda.solicitudes.obtener(ID_SOLICITUD)
            assert anterior is not None and obsoleta is not None
            anterior.aplicar_resultado_evaluacion(
                resultado_solicitud(),
                id_evento=UUID(int=80),
                instante=INSTANTE + timedelta(seconds=2),
            )
            obsoleta.aplicar_resultado_evaluacion(
                resultado_solicitud(),
                id_evento=UUID(int=81),
                instante=INSTANTE + timedelta(seconds=3),
            )
            primera.solicitudes.guardar(anterior)
            for evento in anterior.retirar_eventos():
                primera.registrar_salida(evento)
            primera.confirmar()
            for evento in obsoleta.retirar_eventos():
                segunda.registrar_salida(evento)
            segunda.solicitudes.guardar(obsoleta)
            segunda.confirmar()
    with base.session_factory() as sesion:
        assert list(sesion.scalars(select(SalidaSQL.id_evento))) == [UUID(int=80)]
