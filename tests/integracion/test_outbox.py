from datetime import timedelta

from sqlalchemy import func, select, update

from solicitudes_partner.config.database import Database
from solicitudes_partner.config.persistencia import crear_uow_solicitudes
from solicitudes_partner.seedwork.infraestructura.outbox import RepositorioOutbox, SalidaSQL
from tests.unitarias.dominio.datos import registro


def test_reserva_vencida_no_modifica_reserva_nueva(base: Database) -> None:
    with crear_uow_solicitudes(base) as unidad:
        unidad.destinos = lambda evento: ("reglas_partner.evaluar",)
        unidad.registrar_salida(registro())
        unidad.confirmar()
    outbox = RepositorioOutbox(base.session_factory)
    primera = outbox.reclamar("A", 1, timedelta(seconds=30))[0]
    assert outbox.reclamar("B", 1, timedelta(seconds=30)) == []
    with base.engine.begin() as conexion:
        conexion.execute(
            update(SalidaSQL).values(vence_en=func.clock_timestamp() - timedelta(seconds=1))
        )
    segunda = outbox.reclamar("B", 1, timedelta(seconds=30))[0]
    assert primera.id == segunda.id and primera.token != segunda.token
    assert not outbox.confirmar(primera)
    assert not outbox.reprogramar(primera, "tarde", timedelta(seconds=1))
    assert outbox.confirmar(segunda)
    assert outbox.reclamar("C", 1, timedelta(seconds=30)) == []
    with base.session_factory() as sesion:
        fila = sesion.scalar(select(SalidaSQL))
        assert fila is not None and fila.intentos == 2 and fila.enviada_en is not None


def test_destinos_independientes_y_reintento_conserva_identidad(base: Database) -> None:
    unidad = crear_uow_solicitudes(base)
    unidad.destinos = lambda evento: ("destino.uno", "destino.dos")
    with unidad:
        unidad.registrar_salida(registro())
        unidad.confirmar()
    outbox = RepositorioOutbox(base.session_factory)
    reservas = outbox.reclamar("A", 2, timedelta(seconds=30))
    assert len({reserva.id for reserva in reservas}) == 2
    assert len({reserva.publicacion.id_evento for reserva in reservas}) == 1
    assert outbox.confirmar(reservas[0])
    assert outbox.reprogramar(reservas[1], "broker no disponible", timedelta(0))
    base.engine.dispose()
    repetida = outbox.reclamar("B", 2, timedelta(seconds=30))
    assert len(repetida) == 1
    assert repetida[0].publicacion == reservas[1].publicacion
    assert outbox.metricas()["pendientes"] == 1
    assert outbox.inspeccionar()[0]["ultimo_error"] == "broker no disponible"


def test_reclamadores_concurrentes_distribuyen_lote(base: Database) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from dataclasses import replace
    from threading import Barrier
    from uuid import UUID, uuid4

    with crear_uow_solicitudes(base) as unidad:
        unidad.destinos = lambda evento: ("reglas_partner.evaluar",)
        for _ in range(10):
            unidad.registrar_salida(replace(registro(), id_evento=uuid4()))
        unidad.confirmar()
    barrera = Barrier(2)
    outbox = RepositorioOutbox(base.session_factory)

    def reclamar(propietario: str) -> set[UUID]:
        barrera.wait(timeout=5)
        return {reserva.id for reserva in outbox.reclamar(propietario, 5, timedelta(seconds=30))}

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        primera, segunda = list(ejecutor.map(reclamar, ["A", "B"]))
    assert len(primera | segunda) == 10 and not primera & segunda


def test_despacho_sin_transaccion_abierta_y_sin_acuse(base: Database) -> None:
    from sqlalchemy.pool import QueuePool

    from solicitudes_partner.seedwork.aplicacion.publicacion import Publicacion
    from solicitudes_partner.seedwork.infraestructura.despacho_outbox import DespachadorOutbox

    class Transporte:
        confirmar = False
        publicaciones: list[Publicacion] = []

        def publicar(self, publicacion: Publicacion) -> bool:
            assert isinstance(base.engine.pool, QueuePool)
            assert base.engine.pool.checkedout() == 0
            self.publicaciones.append(publicacion)
            return self.confirmar

    with crear_uow_solicitudes(base) as unidad:
        unidad.destinos = lambda evento: ("reglas_partner.evaluar",)
        unidad.registrar_salida(registro())
        unidad.confirmar()
    transporte = Transporte()
    outbox = RepositorioOutbox(base.session_factory)
    despacho = DespachadorOutbox(outbox, transporte, "prueba", demora_reintento=timedelta(0))
    assert despacho.despachar_lote() == 0
    assert outbox.metricas()["pendientes"] == 1
    transporte.confirmar = True
    assert despacho.despachar_lote() == 1
    assert transporte.publicaciones[0] == transporte.publicaciones[1]
    assert outbox.metricas()["pendientes"] == 0


def test_caida_despues_de_enviar_antes_de_marcar(base: Database) -> None:
    from unittest.mock import patch

    import pytest

    from solicitudes_partner.seedwork.aplicacion.publicacion import Publicacion
    from solicitudes_partner.seedwork.infraestructura.despacho_outbox import DespachadorOutbox

    entregadas: list[Publicacion] = []

    class Transporte:
        def publicar(self, publicacion: Publicacion) -> bool:
            entregadas.append(publicacion)
            return True

    with crear_uow_solicitudes(base) as unidad:
        unidad.destinos = lambda evento: ("reglas_partner.evaluar",)
        unidad.registrar_salida(registro())
        unidad.confirmar()
    outbox = RepositorioOutbox(base.session_factory)
    despacho = DespachadorOutbox(outbox, Transporte(), "A")
    with patch.object(outbox, "confirmar", side_effect=RuntimeError("Caida")):
        with pytest.raises(RuntimeError, match="Caida"):
            despacho.despachar_lote()
    assert outbox.metricas()["pendientes"] == 1
    with base.engine.begin() as conexion:
        conexion.execute(
            update(SalidaSQL).values(vence_en=func.clock_timestamp() - timedelta(seconds=1))
        )
    base.engine.dispose()
    assert despacho.despachar_lote() == 1
    assert entregadas[0] == entregadas[1]


def test_destinos_desconocidos_solo_bloquean_mientras_estan_pendientes(base: Database) -> None:
    import pytest

    from solicitudes_partner.config.persistencia import verificar_destinos

    outbox = RepositorioOutbox(base.session_factory)
    admitidos = ("reglas_partner.evaluar",)
    assert not outbox.hay_pendientes_fuera_de(admitidos)
    with crear_uow_solicitudes(base) as unidad:
        unidad.destinos = lambda evento: ("reglas_partner.evaluar",)
        unidad.registrar_salida(registro())
        unidad.confirmar()
    assert not outbox.hay_pendientes_fuera_de(admitidos)
    verificar_destinos(base)
    with base.engine.begin() as conexion:
        conexion.execute(
            update(SalidaSQL).values(
                destino="laboratorio.anterior",
                proximo_intento=func.clock_timestamp() + timedelta(hours=1),
            )
        )
    assert outbox.hay_pendientes_fuera_de(admitidos)
    with pytest.raises(ValueError, match="destinos pendientes desconocidos"):
        verificar_destinos(base)
    with base.engine.begin() as conexion:
        conexion.execute(update(SalidaSQL).values(enviada_en=func.clock_timestamp()))
    assert not outbox.hay_pendientes_fuera_de(admitidos)
    verificar_destinos(base)
