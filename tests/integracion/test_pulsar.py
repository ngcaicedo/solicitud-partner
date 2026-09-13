import json
import os
import sqlite3
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from time import monotonic, sleep
from typing import Any
from uuid import uuid4

import pulsar
import pytest
from pulsar.schema import AvroSchema
from sqlalchemy import func, select, update

from solicitudes_partner.config.database import Database
from solicitudes_partner.config.persistencia import crear_uow_reglas, crear_uow_solicitudes
from solicitudes_partner.config.procesamiento import iniciar_despacho_interno, iniciar_publicacion
from solicitudes_partner.config.serializacion import decodificar_evento
from solicitudes_partner.config.settings import Settings
from solicitudes_partner.modulos.solicitudes.aplicacion.comandos import RegistrarSolicitudPartner
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import EstadoSolicitud
from solicitudes_partner.modulos.solicitudes.infraestructura.esquemas.v1.eventos import (
    SolicitudListaV1,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.mapeadores_eventos import (
    evento_integracion,
)
from solicitudes_partner.seedwork.infraestructura.despacho_outbox import DespachadorOutbox
from solicitudes_partner.seedwork.infraestructura.outbox import RepositorioOutbox, SalidaSQL
from solicitudes_partner.seedwork.infraestructura.publicador_pulsar import PublicadorPulsar
from tests.integracion.datos import flujo_sql
from tests.unitarias.dominio.datos import datos_solicitud, politica

RAIZ = Path(__file__).resolve().parents[2]


def esperar(condicion: Callable[[], bool], segundos: float = 10) -> None:
    plazo = monotonic() + segundos
    while monotonic() < plazo:
        if condicion():
            return
        sleep(0.05)
    raise AssertionError("No se cumplio la condicion dentro del plazo")


@pytest.fixture
def transporte() -> Iterator[tuple[Any, Settings]]:
    url = os.getenv("PARTNER_TEST_PULSAR_URL", "pulsar://127.0.0.1:6650")
    topico = "persistent://public/default/prueba-partner-" + uuid4().hex
    cliente = pulsar.Client(url, operation_timeout_seconds=3, connection_timeout_ms=1000)
    try:
        productor = cliente.create_producer(topico)
        productor.close()
    except Exception:
        cliente.close()
        pytest.fail("Pulsar requerido: docker compose up -d --wait pulsar", pytrace=False)
    try:
        yield (
            cliente,
            Settings(pulsar_url=url, topico_solicitudes=topico, topico_lectura=topico + "-lectura"),
        )
    finally:
        cliente.close()
        import urllib.request

        admin = os.getenv("PARTNER_TEST_PULSAR_ADMIN_URL", "http://127.0.0.1:18086")
        for nombre_topico in (topico, topico + "-lectura"):
            peticion = urllib.request.Request(
                admin
                + "/admin/v2/persistent/public/default/"
                + nombre_topico.rsplit("/", 1)[1]
                + "?force=true",
                method="DELETE",
            )
            try:
                with urllib.request.urlopen(peticion, timeout=5):
                    pass
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise


def cantidad(archivo: Path) -> int:
    with sqlite3.connect(archivo) as conexion:
        return int(conexion.execute("SELECT count(*) FROM recibidos").fetchone()[0])


def consumir(
    configuracion: Settings, suscripcion: str, archivo: Path, fallar: bool = False
) -> subprocess.CompletedProcess[str]:
    comando = [
        sys.executable,
        str(RAIZ / "scripts/consumir_eventos.py"),
        "--url",
        configuracion.pulsar_url,
        "--topico",
        configuracion.topico_solicitudes,
        "--suscripcion",
        suscripcion,
        "--base",
        str(archivo),
    ]
    if fallar:
        comando.append("--interrumpir-tras-commit")
    return subprocess.run(comando, capture_output=True, text=True, timeout=25)


def test_automatico_dos_suscripciones_y_reinicio_tras_commit(
    base: Database, transporte: tuple[Any, Settings], tmp_path: Path
) -> None:
    cliente, configuracion = transporte
    for nombre in ("atencion", "estadisticas"):
        consumidor = cliente.subscribe(
            configuracion.topico_solicitudes,
            nombre,
            initial_position=pulsar.InitialPosition.Earliest,
            consumer_type=pulsar.ConsumerType.Shared,
        )
        consumidor.close()
    with crear_uow_reglas(base) as unidad:
        unidad.politicas.guardar(politica())
        unidad.confirmar()
    interno = iniciar_despacho_interno(base, pausa=0.02)
    externo = iniciar_publicacion(base, configuracion)
    try:
        flujo_sql(base).registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
        primera = consumir(configuracion, "atencion", tmp_path / "atencion.db", fallar=True)
        assert primera.returncode == 75, primera.stderr
        assert cantidad(tmp_path / "atencion.db") == 1
        segunda = consumir(configuracion, "atencion", tmp_path / "atencion.db")
        assert segunda.returncode == 0, segunda.stderr
        assert cantidad(tmp_path / "atencion.db") == 1
        tardia = consumir(configuracion, "estadisticas", tmp_path / "estadisticas.db")
        assert tardia.returncode == 0, tardia.stderr
        assert cantidad(tmp_path / "estadisticas.db") == 1
        esperar(lambda: RepositorioOutbox(base.session_factory).metricas()["pendientes"] == 2)
    finally:
        interno.detener()
        externo.detener()
    assert not interno.hilo.is_alive() and not externo.hilo.is_alive()


def test_publicado_sin_marca_se_reenvia_con_mismo_id(
    base: Database, transporte: tuple[Any, Settings], tmp_path: Path
) -> None:
    from unittest.mock import patch

    cliente, configuracion = transporte
    consumidor = cliente.subscribe(
        configuracion.topico_solicitudes,
        "reentrega",
        initial_position=pulsar.InitialPosition.Earliest,
    )
    import runpy

    persistir = runpy.run_path(str(RAIZ / "scripts/consumir_eventos.py"))["persistir"]
    esquema = json.loads((RAIZ / "docs/contratos/solicitud-lista-v1.avsc").read_text())
    with crear_uow_reglas(base) as unidad:
        unidad.politicas.guardar(politica())
        unidad.confirmar()
    interno = iniciar_despacho_interno(base, pausa=0.02)
    publicador = PublicadorPulsar(
        configuracion.pulsar_url,
        configuracion.topico_solicitudes,
        AvroSchema(SolicitudListaV1),
        lambda documento: evento_integracion(decodificar_evento(documento)),
    )
    outbox = RepositorioOutbox(base.session_factory, ("integracion.solicitud_lista.v1",))
    despacho = DespachadorOutbox(outbox, publicador, "prueba")
    try:
        flujo_sql(base).registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))

        def lista() -> bool:
            with base.session_factory() as sesion:
                return (
                    sesion.scalar(
                        select(SalidaSQL.id).where(
                            SalidaSQL.destino == "integracion.solicitud_lista.v1"
                        )
                    )
                    is not None
                )

        esperar(lista)
        with patch.object(outbox, "confirmar", side_effect=RuntimeError("caida")):
            with pytest.raises(RuntimeError, match="caida"):
                despacho.despachar_lote(1)
        primero = consumidor.receive(timeout_millis=5000)
        identidad = persistir(primero.data(), esquema, tmp_path / "recibidos.db")
        consumidor.acknowledge(primero)
        with base.engine.begin() as conexion:
            conexion.execute(
                update(SalidaSQL)
                .where(SalidaSQL.destino == "integracion.solicitud_lista.v1")
                .values(vence_en=func.clock_timestamp() - timedelta(seconds=1))
            )
        assert despacho.despachar_lote(1) == 1
        segundo = consumidor.receive(timeout_millis=5000)
        assert persistir(segundo.data(), esquema, tmp_path / "recibidos.db") == identidad
        consumidor.acknowledge(segundo)
        assert cantidad(tmp_path / "recibidos.db") == 1
    finally:
        interno.detener()
        publicador.cerrar()
        consumidor.close()


def test_broker_detenido_no_bloquea_flujo_interno(
    base: Database, transporte: tuple[Any, Settings], tmp_path: Path
) -> None:
    cliente, configuracion = transporte
    assert configuracion.pulsar_url == "pulsar://127.0.0.1:6650", (
        "Este ensayo controla solo el Compose local"
    )
    consumidor = cliente.subscribe(
        configuracion.topico_solicitudes,
        "recuperacion",
        initial_position=pulsar.InitialPosition.Earliest,
    )
    consumidor.close()
    with crear_uow_reglas(base) as unidad:
        unidad.politicas.guardar(politica())
        unidad.confirmar()
    from solicitudes_partner.config.bootstrap import componer_proyeccion
    from solicitudes_partner.config.procesamiento import (
        iniciar_proyeccion,
        iniciar_publicacion_cqrs,
    )
    from solicitudes_partner.modulos.solicitudes.infraestructura.repositorios import (
        RepositorioLecturaSQL,
    )

    preparacion = componer_proyeccion(base, configuracion)
    preparacion.abrir()
    preparacion.cerrar()
    cqrs = iniciar_publicacion_cqrs(base, configuracion)
    proyeccion = iniciar_proyeccion(base, configuracion)
    interno = iniciar_despacho_interno(base, pausa=0.02)
    externo = iniciar_publicacion(base, configuracion)
    try:
        subprocess.run(
            ["docker", "compose", "stop", "pulsar"],
            cwd=RAIZ,
            check=True,
            capture_output=True,
            timeout=40,
        )
        confirmacion = flujo_sql(base).registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
        rechazo = flujo_sql(base).registrar(
            RegistrarSolicitudPartner(
                datos=replace(datos_solicitud(False), referencia_externa="RECHAZO")
            )
        )

        def terminadas() -> bool:
            with crear_uow_solicitudes(base) as unidad:
                lista = unidad.solicitudes.obtener(confirmacion.id_solicitud)
                rechazada = unidad.solicitudes.obtener(rechazo.id_solicitud)
                return (
                    lista is not None
                    and lista.estado is EstadoSolicitud.LISTA_PARA_ATENCION
                    and rechazada is not None
                    and rechazada.estado is EstadoSolicitud.RECHAZADA
                )

        esperar(terminadas)
        esperar(lambda: RepositorioOutbox(base.session_factory).metricas()["pendientes"] == 5)
        subprocess.run(
            ["docker", "compose", "up", "-d", "--wait", "pulsar"],
            cwd=RAIZ,
            check=True,
            capture_output=True,
            timeout=100,
        )
        resultado = consumir(configuracion, "recuperacion", tmp_path / "recuperacion.db")
        assert resultado.returncode == 0, resultado.stderr
        esperar(lambda: RepositorioOutbox(base.session_factory).metricas()["pendientes"] == 0)
        assert cantidad(tmp_path / "recuperacion.db") == 1
        lectura = RepositorioLecturaSQL(base.session_factory)
        esperar(
            lambda: (
                {vista.estado for vista in lectura.listar(datos_solicitud().id_partner, 20, 0)}
                == {
                    EstadoSolicitud.LISTA_PARA_ATENCION,
                    EstadoSolicitud.RECHAZADA,
                }
            )
        )
    finally:
        interno.detener()
        externo.detener()
        cqrs.detener()
        proyeccion.detener()
        subprocess.run(
            ["docker", "compose", "up", "-d", "--wait", "pulsar"],
            cwd=RAIZ,
            check=True,
            capture_output=True,
            timeout=100,
        )
