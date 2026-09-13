import json
import os
import signal
import socket
import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from time import monotonic, sleep
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import select

from solicitudes_partner.config.bootstrap import componer_proyeccion
from solicitudes_partner.config.database import Database
from solicitudes_partner.config.persistencia import crear_uow_reglas
from solicitudes_partner.config.settings import Settings
from solicitudes_partner.modulos.solicitudes.infraestructura.vistas import VistaSolicitudSQL
from solicitudes_partner.seedwork.infraestructura.outbox import SalidaSQL
from tests.unitarias.dominio.datos import ID_PARTNER, politica

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def configuracion_cqrs(base: Database) -> Iterator[Settings]:
    nombre = "prueba-cqrs-" + uuid4().hex
    configuracion = Settings(
        database_url=base.engine.url.render_as_string(hide_password=False),
        pulsar_url=os.getenv("PARTNER_TEST_PULSAR_URL", "pulsar://127.0.0.1:6650"),
        topico_lectura="persistent://public/default/" + nombre,
        topico_solicitudes="persistent://public/default/" + nombre + "-publico",
        suscripcion_lectura="vista",
    )
    try:
        yield configuracion
    finally:
        admin = os.getenv("PARTNER_TEST_PULSAR_ADMIN_URL", "http://127.0.0.1:18086")
        with httpx2.Client(timeout=5) as cliente:
            for topico in (configuracion.topico_lectura, configuracion.topico_solicitudes):
                respuesta = cliente.delete(
                    admin
                    + "/admin/v2/persistent/public/default/"
                    + topico.rsplit("/", 1)[1]
                    + "?force=true"
                )
                if respuesta.status_code != 404:
                    respuesta.raise_for_status()


def esperar_http(cliente: httpx2.Client, ruta: str, estado: str | None = None) -> dict[str, Any]:
    plazo = monotonic() + 20
    while monotonic() < plazo:
        try:
            respuesta = cliente.get(ruta)
            if respuesta.status_code == 200:
                documento: dict[str, Any] = respuesta.json()
                if estado is None or documento.get("estado") == estado:
                    return documento
        except httpx2.RequestError:
            pass
        sleep(0.05)
    raise AssertionError(f"HTTP no convergio para {ruta}: {estado}")


def test_http_un_proceso_y_recuperacion(
    base: Database,
    configuracion_cqrs: Settings,
    tmp_path: Path,
) -> None:
    with socket.socket() as puerto_libre:
        puerto_libre.bind(("127.0.0.1", 0))
        puerto = puerto_libre.getsockname()[1]
    entorno = dict(
        os.environ,
        PARTNER_DATABASE_URL=str(configuracion_cqrs.database_url),
        PARTNER_PULSAR_URL=configuracion_cqrs.pulsar_url,
        PARTNER_PULSAR_TOPIC=configuracion_cqrs.topico_solicitudes,
        PARTNER_CQRS_TOPIC=configuracion_cqrs.topico_lectura,
        PARTNER_CQRS_SUBSCRIPTION=configuracion_cqrs.suscripcion_lectura,
    )
    procesos: list[subprocess.Popen[str]] = []
    registros = []

    def iniciar(nombre: str, argumentos: list[str]) -> subprocess.Popen[str]:
        archivo = (tmp_path / (nombre + ".log")).open("w")
        registros.append(archivo)
        proceso = subprocess.Popen(
            [sys.executable, "-m", *argumentos],
            cwd=RAIZ,
            env=entorno,
            stdout=archivo,
            stderr=subprocess.STDOUT,
            text=True,
        )
        procesos.append(proceso)
        return proceso

    def detener(proceso: subprocess.Popen[str]) -> None:
        if proceso.poll() is None:
            proceso.terminate()
            proceso.wait(timeout=25)

    try:
        argumentos_api = [
            "uvicorn",
            "solicitudes_partner.api.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(puerto),
        ]
        api = iniciar("api", argumentos_api)
        with httpx2.Client(
            base_url=f"http://127.0.0.1:{puerto}",
            headers={"X-Partner-Laboratorio": str(ID_PARTNER)},
            timeout=5,
        ) as cliente:
            esperar_http(cliente, "/health/live")
            datos = dict(
                referencia_externa="PENDIENTE",
                categoria="plomeria",
                tipo="SINIESTRO",
                aprobacion_previa=True,
            )
            aceptada = cliente.post("/solicitudes", json=datos)
            assert aceptada.status_code == 202
            ubicacion = aceptada.headers["location"]
            recibida = esperar_http(cliente, ubicacion, "RECIBIDA")
            assert recibida["tipo_red"] is recibida["resultado"] is recibida["motivo"] is None
            detener(api)
            with crear_uow_reglas(base) as unidad:
                unidad.politicas.guardar(politica())
                unidad.confirmar()
            iniciar("api-reinicio", argumentos_api)
            lista = esperar_http(cliente, ubicacion, "LISTA_PARA_ATENCION")
            assert lista["tipo_red"] == "GENERAL_HDA" and lista["motivo"] is None
            assert cliente.post("/solicitudes", json=datos).json() == aceptada.json()
            assert (
                cliente.post("/solicitudes", json=datos | {"categoria": "otra"}).status_code == 409
            )
            assert (
                cliente.get(ubicacion, headers={"X-Partner-Laboratorio": str(uuid4())}).status_code
                == 404
            )
            rechazo = cliente.post(
                "/solicitudes",
                json=datos | {"referencia_externa": "RECHAZADA", "aprobacion_previa": False},
            )
            assert rechazo.status_code == 202
            id_rechazo = rechazo.json()["id_solicitud"]
            with base.session_factory() as sesion:
                assert (
                    sesion.scalar(
                        select(SalidaSQL.id).where(
                            SalidaSQL.destino == "integracion.solicitud_lista.v1",
                            SalidaSQL.documento["id_solicitud"].astext == str(id_rechazo),
                        )
                    )
                    is None
                )
            rechazada = esperar_http(cliente, rechazo.headers["location"], "RECHAZADA")
            assert (
                rechazada["motivo"] == "APROBACION_PREVIA_REQUERIDA"
                and rechazada["tipo_red"] is None
            )
            assert rechazada["version_politica"] == 1
            assert len(cliente.get("/solicitudes").json()) == 2
            assert (
                cliente.get("/solicitudes", headers={"X-Partner-Laboratorio": str(uuid4())}).json()
                == []
            )
            primera = cliente.get("/solicitudes?limite=1").json()
            segunda = cliente.get("/solicitudes?limite=1&desplazamiento=1").json()
            assert primera[0]["id_solicitud"] != segunda[0]["id_solicitud"]
        with base.session_factory() as sesion:
            filas = list(sesion.scalars(select(VistaSolicitudSQL)))
            assert len(filas) == 2
            print(
                "CQRS HTTP: "
                + json.dumps(
                    {
                        "vistas": len(filas),
                        "procesos_simultaneos": 1,
                        "recuperacion": "sin reinicializar datos",
                        "latencias_finales_segundos": [
                            round(
                                (
                                    fila.proyectada_en
                                    - datetime.fromisoformat(fila.documento["actualizada_en"])
                                ).total_seconds(),
                                6,
                            )
                            for fila in filas
                        ],
                    }
                )
            )
    finally:
        for proceso in reversed(procesos):
            detener(proceso)
        for archivo in registros:
            archivo.close()
        for ruta_log in tmp_path.glob("api*.log"):
            assert "Application shutdown complete" in ruta_log.read_text()
        for proceso in procesos:
            codigo_esperado = -signal.SIGTERM
            assert proceso.returncode in (0, codigo_esperado), "\n".join(
                archivo.read_text() for archivo in tmp_path.glob("*.log")
            )


def test_reentrega_tras_commit_no_repite_vista(
    base: Database,
    configuracion_cqrs: Settings,
) -> None:
    from unittest.mock import patch

    import pulsar
    from pulsar.schema import AvroSchema
    from sqlalchemy import func

    from solicitudes_partner.config.serializacion import serializar_evento
    from solicitudes_partner.modulos.solicitudes.infraestructura.esquemas.v1.lectura import (
        SolicitudLecturaV1,
    )
    from solicitudes_partner.modulos.solicitudes.infraestructura.mapeadores_eventos import (
        mensaje_lectura,
    )
    from solicitudes_partner.seedwork.infraestructura.inbox import EntradaSQL
    from tests.unitarias.dominio.datos import registro

    cliente = pulsar.Client(configuracion_cqrs.pulsar_url)
    consumidor = componer_proyeccion(base, configuracion_cqrs)
    try:
        consumidor.abrir()
        productor = cliente.create_producer(
            configuracion_cqrs.topico_lectura, schema=AvroSchema(SolicitudLecturaV1)
        )
        productor.send(mensaje_lectura(serializar_evento(registro())))
        original = consumidor.proyector.proyectar

        def confirmar_y_fallar(actualizacion: Any) -> None:
            original(actualizacion)
            raise RuntimeError("Caida despues del commit")

        with patch.object(consumidor.proyector, "proyectar", side_effect=confirmar_y_fallar):
            with pytest.raises(RuntimeError, match="despues del commit"):
                consumidor.procesar_siguiente()
        consumidor.cerrar()
        consumidor = componer_proyeccion(base, configuracion_cqrs)
        plazo = monotonic() + 10
        while not consumidor.procesar_siguiente():
            assert monotonic() < plazo
        with base.session_factory() as sesion:
            assert sesion.scalar(select(func.count()).select_from(VistaSolicitudSQL)) == 1
            assert sesion.scalar(select(func.count()).select_from(EntradaSQL)) == 1
    finally:
        consumidor.cerrar()
        cliente.close()
