from datetime import timedelta
from uuid import UUID

import pytest

from tests.unitarias.aplicacion.dobles.unidad_trabajo import (
    AlmacenMemoria,
    EstadoSolicitudes,
    UnidadTrabajoSolicitudesMemoria,
)
from tests.unitarias.dominio.datos import ID_SOLICITUD, INSTANTE, resultado, solicitud_nueva


@pytest.mark.parametrize("fallar", [False, True])
def test_confirmacion_atomica_de_solicitud_y_salida(fallar: bool) -> None:
    almacen = AlmacenMemoria(EstadoSolicitudes(), fallar_confirmacion=fallar)
    with UnidadTrabajoSolicitudesMemoria(almacen) as unidad:
        solicitud = solicitud_nueva()
        unidad.solicitudes.guardar(solicitud)
        for evento in solicitud.retirar_eventos():
            unidad.registrar_salida(evento)
        assert almacen.estado.solicitudes.obtener(ID_SOLICITUD) is None
        assert almacen.estado.salidas == []
        if fallar:
            with pytest.raises(RuntimeError, match="Fallo de confirmacion"):
                unidad.confirmar()
        else:
            unidad.confirmar()
    assert len(almacen.estado.salidas) == (0 if fallar else 1)
    assert (almacen.estado.solicitudes.obtener(ID_SOLICITUD) is None) == fallar


@pytest.mark.parametrize("terminacion", ["sin_confirmar", "excepcion", "rollback", "fallo_commit"])
def test_actualizacion_no_filtra_mutaciones_ni_pendientes(terminacion: str) -> None:
    almacen = AlmacenMemoria(EstadoSolicitudes())
    original = solicitud_nueva()
    original.retirar_eventos()
    almacen.estado.solicitudes.guardar(original)
    try:
        with UnidadTrabajoSolicitudesMemoria(almacen) as unidad:
            copia = unidad.solicitudes.obtener(ID_SOLICITUD)
            assert copia is not None and copia is not original
            copia.aplicar_resultado_evaluacion(
                resultado(), id_evento=UUID(int=30), instante=INSTANTE + timedelta(seconds=2)
            )
            for evento in copia.retirar_eventos():
                unidad.registrar_salida(evento)
            if terminacion == "excepcion":
                raise RuntimeError("Interrumpida")
            if terminacion == "rollback":
                unidad.revertir()
            if terminacion == "fallo_commit":
                almacen.fallar_confirmacion = True
                unidad.confirmar()
    except RuntimeError:
        assert terminacion in {"excepcion", "fallo_commit"}
    conservada = almacen.estado.solicitudes.obtener(ID_SOLICITUD)
    assert conservada is not None
    assert conservada.version == 1 and conservada.evaluacion is None
    assert conservada.eventos_pendientes == () and almacen.estado.salidas == []


def test_confirmacion_no_expone_instancia_modificable_y_uow_nueva_ve_estado() -> None:
    almacen = AlmacenMemoria(EstadoSolicitudes())
    with UnidadTrabajoSolicitudesMemoria(almacen) as unidad:
        solicitud = solicitud_nueva()
        unidad.solicitudes.guardar(solicitud)
        unidad.confirmar()
    solicitud.aplicar_resultado_evaluacion(
        resultado(), id_evento=UUID(int=30), instante=INSTANTE + timedelta(seconds=2)
    )
    with UnidadTrabajoSolicitudesMemoria(almacen) as siguiente:
        conservada = siguiente.solicitudes.obtener(ID_SOLICITUD)
        assert conservada is not None and conservada.version == 1


def test_error_al_transferir_conserva_salida_confirmada_hasta_reintento() -> None:
    from solicitudes_partner.seedwork.dominio.eventos import EventoDominio
    from solicitudes_partner.seedwork.infraestructura.bus_eventos_local import BusEventosLocal

    class BusInterrumpido(BusEventosLocal):
        fallar = True

        def publicar(self, evento: EventoDominio) -> None:
            if self.fallar:
                raise RuntimeError("Transferencia interrumpida")
            super().publicar(evento)

    almacen = AlmacenMemoria(EstadoSolicitudes())
    with UnidadTrabajoSolicitudesMemoria(almacen) as unidad:
        solicitud = solicitud_nueva()
        unidad.solicitudes.guardar(solicitud)
        for evento in solicitud.retirar_eventos():
            unidad.registrar_salida(evento)
        unidad.confirmar()
    original = almacen.estado.salidas[0]
    bus = BusInterrumpido()
    with pytest.raises(RuntimeError, match="Transferencia interrumpida"):
        almacen.transferir_salidas(bus)
    assert almacen.estado.salidas == [original]
    bus.fallar = False
    almacen.transferir_salidas(bus)
    almacen.transferir_salidas(bus)
    assert bus.publicados == (original,) and almacen.estado.salidas == []
