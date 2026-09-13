import pytest

from solicitudes_partner.modulos.solicitudes.dominio.eventos import (
    SolicitudPartnerRegistrada,
)
from solicitudes_partner.seedwork.infraestructura.bus_eventos_local import BusEventosLocal
from tests.unitarias.dominio.datos import registro


def test_publicacion_encola_para_cada_suscriptor_sin_ejecutarlo() -> None:
    bus = BusEventosLocal()
    recibidos: list[SolicitudPartnerRegistrada] = []
    bus.suscribir(SolicitudPartnerRegistrada, "primero", recibidos.append)
    bus.suscribir(SolicitudPartnerRegistrada, "segundo", recibidos.append)
    evento = registro()
    bus.publicar(evento)
    assert recibidos == [] and len(bus.pendientes) == 2
    assert bus.despachar_siguiente()
    assert recibidos == [evento] and len(bus.pendientes) == 1
    assert bus.despachar_siguiente()
    assert recibidos == [evento, evento]
    assert not bus.despachar_siguiente()


def test_fallo_conserva_entrega_y_no_repite_consumidor_completado() -> None:
    bus = BusEventosLocal()
    recibidos: list[str] = []
    fallar = True

    def inestable(evento: SolicitudPartnerRegistrada) -> None:
        if fallar:
            raise RuntimeError("Consumidor fallo")
        recibidos.append("segundo")

    bus.suscribir(SolicitudPartnerRegistrada, "primero", lambda evento: recibidos.append("primero"))
    bus.suscribir(SolicitudPartnerRegistrada, "segundo", inestable)
    bus.suscribir(SolicitudPartnerRegistrada, "tercero", lambda evento: recibidos.append("tercero"))
    bus.publicar(registro())
    bus.despachar_siguiente()
    with pytest.raises(RuntimeError, match="Consumidor fallo"):
        bus.despachar_siguiente()
    assert [entrega.consumidor for entrega in bus.pendientes] == ["segundo", "tercero"]
    assert recibidos == ["primero"]
    fallar = False
    bus.despachar_siguiente()
    bus.despachar_siguiente()
    assert recibidos == ["primero", "segundo", "tercero"]


def test_salida_sin_destinatarios_permanece_observable_y_buses_aislados() -> None:
    bus = BusEventosLocal()
    evento = registro()
    bus.publicar(evento)
    assert bus.publicados == (evento,) and bus.sin_suscriptores == (evento,)
    assert not bus.despachar_siguiente()
    assert BusEventosLocal().publicados == ()


def test_publicar_desde_handler_no_produce_recursion() -> None:
    bus = BusEventosLocal()
    recibidos: list[SolicitudPartnerRegistrada] = []

    def publicar_otro(evento: SolicitudPartnerRegistrada) -> None:
        recibidos.append(evento)
        if len(recibidos) == 1:
            bus.publicar(evento)

    bus.suscribir(SolicitudPartnerRegistrada, "primero", publicar_otro)
    bus.publicar(registro())
    bus.despachar_siguiente()
    assert len(recibidos) == 1 and len(bus.pendientes) == 1
    bus.despachar_siguiente()
    assert len(recibidos) == 2


def test_no_sobrescribe_suscripcion_y_prohibe_despacho_reentrante() -> None:
    bus = BusEventosLocal()

    def recursivo(evento: SolicitudPartnerRegistrada) -> None:
        bus.despachar_siguiente()

    bus.suscribir(SolicitudPartnerRegistrada, "primero", recursivo)
    with pytest.raises(ValueError):
        bus.suscribir(SolicitudPartnerRegistrada, "primero", recursivo)
    bus.publicar(registro())
    with pytest.raises(RuntimeError):
        bus.despachar_siguiente()
    assert len(bus.pendientes) == 1
