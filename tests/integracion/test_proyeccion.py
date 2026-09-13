from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from solicitudes_partner.config.database import Database
from solicitudes_partner.modulos.solicitudes.aplicacion.vistas import ActualizacionVista
from solicitudes_partner.modulos.solicitudes.infraestructura.mapeadores import (
    actualizacion_desde_evento,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.proyecciones import (
    ProyectorSolicitudes,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.repositorios import (
    RepositorioLecturaSQL,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.vistas import VistaSolicitudSQL
from solicitudes_partner.seedwork.infraestructura.inbox import EntradaSQL
from tests.unitarias.dominio.datos import (
    ID_PARTNER,
    ID_SOLICITUD,
    INSTANTE,
    registro,
    solicitud_nueva,
)
from tests.unitarias.dominio.datos_resultados import resultado_solicitud


def actualizacion_final(aprobacion: bool = True) -> ActualizacionVista:
    solicitud = solicitud_nueva(aprobacion)
    solicitud.retirar_eventos()
    solicitud.aplicar_resultado_evaluacion(
        resultado_solicitud(aprobacion), id_evento=uuid4(), instante=INSTANTE + timedelta(seconds=2)
    )
    return actualizacion_desde_evento(solicitud.retirar_eventos()[0])


@pytest.mark.parametrize("aprobacion", [True, False])
def test_proyecta_final_sin_registro_y_no_retrocede(base: Database, aprobacion: bool) -> None:
    proyector = ProyectorSolicitudes(base.session_factory)
    final = actualizacion_final(aprobacion)
    assert proyector.proyectar(final)
    assert not proyector.proyectar(actualizacion_desde_evento(registro(aprobacion)))
    assert not proyector.proyectar(final)
    assert (
        RepositorioLecturaSQL(base.session_factory).obtener(ID_PARTNER, ID_SOLICITUD) == final.vista
    )
    with base.session_factory() as sesion:
        assert sesion.scalar(select(func.count()).select_from(VistaSolicitudSQL)) == 1
        assert sesion.scalar(select(func.count()).select_from(EntradaSQL)) == 2


def test_version_igual_con_otro_contenido_revierte_inbox(base: Database) -> None:
    proyector = ProyectorSolicitudes(base.session_factory)
    final = actualizacion_final()
    proyector.proyectar(final)
    equivalente = replace(final, id_evento=uuid4())
    assert not proyector.proyectar(equivalente)
    contradictoria = replace(final, id_evento=uuid4(), vista=replace(final.vista, categoria="otra"))
    with pytest.raises(ValueError, match="contradictoria"):
        proyector.proyectar(contradictoria)
    with base.session_factory() as sesion:
        assert sesion.get(EntradaSQL, (proyector.consumidor, contradictoria.id_evento)) is None
    assert (
        RepositorioLecturaSQL(base.session_factory).obtener(ID_PARTNER, ID_SOLICITUD) == final.vista
    )


def test_fallo_antes_commit_revierte_vista_e_inbox(base: Database) -> None:
    proyector = ProyectorSolicitudes(base.session_factory)
    with patch.object(Session, "commit", side_effect=RuntimeError("caida")):
        with pytest.raises(RuntimeError, match="caida"):
            proyector.proyectar(actualizacion_final())
    with base.session_factory() as sesion:
        assert sesion.scalar(select(func.count()).select_from(VistaSolicitudSQL)) == 0
        assert sesion.scalar(select(func.count()).select_from(EntradaSQL)) == 0


def test_carrera_de_versiones_conserva_la_mayor(base: Database) -> None:
    proyector = ProyectorSolicitudes(base.session_factory)
    barrera = Barrier(2)
    inicial = actualizacion_desde_evento(registro())
    final = actualizacion_final()

    def proyectar(actualizacion: ActualizacionVista) -> bool:
        barrera.wait(timeout=5)
        return proyector.proyectar(actualizacion)

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        list(ejecutor.map(proyectar, [inicial, final]))
    assert (
        RepositorioLecturaSQL(base.session_factory).obtener(ID_PARTNER, ID_SOLICITUD) == final.vista
    )


def test_filtro_partner_y_orden_de_paginas(base: Database) -> None:
    proyector = ProyectorSolicitudes(base.session_factory)
    final = actualizacion_final()
    proyector.proyectar(final)
    otra = replace(final, id_evento=uuid4(), vista=replace(final.vista, id_solicitud=uuid4()))
    proyector.proyectar(otra)
    ajena = replace(
        final,
        id_evento=uuid4(),
        vista=replace(final.vista, id_solicitud=uuid4(), id_partner=uuid4()),
    )
    proyector.proyectar(ajena)
    repositorio = RepositorioLecturaSQL(base.session_factory)
    assert repositorio.obtener(ajena.vista.id_partner, final.vista.id_solicitud) is None
    pagina = repositorio.listar(ID_PARTNER, limite=1, desplazamiento=0)
    siguiente = repositorio.listar(ID_PARTNER, limite=1, desplazamiento=1)
    assert [vista.id_solicitud for vista in pagina + siguiente] == sorted(
        [final.vista.id_solicitud, otra.vista.id_solicitud]
    )
    assert repositorio.listar(ID_PARTNER, limite=1, desplazamiento=2) == []


def test_mismo_id_con_contenido_distinto_no_cambia_vista(base: Database) -> None:
    proyector = ProyectorSolicitudes(base.session_factory)
    final = actualizacion_final()
    proyector.proyectar(final)
    contradictoria = replace(final, vista=replace(final.vista, categoria="otra"))
    with pytest.raises(ValueError, match="otro contenido"):
        proyector.proyectar(contradictoria)
    assert (
        RepositorioLecturaSQL(base.session_factory).obtener(ID_PARTNER, ID_SOLICITUD) == final.vista
    )
