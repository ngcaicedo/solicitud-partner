from dataclasses import asdict, replace

import pytest

from solicitudes_partner.modulos.reglas_partner.dominio.eventos import (
    ReglasDePartnerEvaluadas,
)
from solicitudes_partner.modulos.reglas_partner.dominio.excepciones import (
    ErrorConfiguracionPolitica,
)
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import (
    TipoRedProveedores,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.comandos import RegistrarSolicitudPartner
from solicitudes_partner.modulos.solicitudes.dominio.eventos import (
    SolicitudPartnerListaParaAtencion,
    SolicitudPartnerRechazada,
    SolicitudPartnerRegistrada,
)
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
    ResultadoEvaluacion,
    TipoSolicitud,
)
from solicitudes_partner.seedwork.infraestructura.bus_eventos_local import BusEventosLocal
from tests.unitarias.aplicacion.datos import Escenario
from tests.unitarias.dominio.datos import ID_PARTNER, datos_solicitud, politica


@pytest.mark.parametrize("red", list(TipoRedProveedores))
@pytest.mark.parametrize(
    "tipo,aprobacion",
    [
        (TipoSolicitud.SINIESTRO, True),
        (TipoSolicitud.SINIESTRO, False),
        (TipoSolicitud.INSTALACION, None),
    ],
)
def test_recorrido_por_etapas_y_reentregas(
    red: TipoRedProveedores, tipo: TipoSolicitud, aprobacion: bool | None
) -> None:
    escenario = Escenario()
    escenario.reglas.estado.politicas.politicas[ID_PARTNER] = politica(red)
    confirmacion = escenario.flujo.registrar(
        RegistrarSolicitudPartner(datos=datos_solicitud(aprobacion, tipo))
    )
    assert escenario.reglas.confirmaciones == 0
    escenario.transferir()
    registro = escenario.bus.publicados[0]
    assert isinstance(registro, SolicitudPartnerRegistrada)
    assert escenario.bus.despachar_siguiente()
    assert escenario.reglas.confirmaciones == 1
    solicitud = escenario.solicitudes.estado.solicitudes.obtener(confirmacion.id_solicitud)
    assert solicitud is not None and solicitud.version == 1
    escenario.transferir()
    evaluacion = escenario.bus.publicados[1]
    assert isinstance(evaluacion, ReglasDePartnerEvaluadas)
    assert escenario.bus.despachar_siguiente()
    escenario.transferir()
    terminal = escenario.bus.publicados[2]
    rechazada = tipo is TipoSolicitud.SINIESTRO and aprobacion is False
    assert isinstance(
        terminal, SolicitudPartnerRechazada if rechazada else SolicitudPartnerListaParaAtencion
    )
    assert isinstance(terminal.evaluacion, ResultadoEvaluacion)
    assert asdict(terminal.evaluacion) == asdict(evaluacion)
    assert (terminal.evaluacion.tipo_red.value if terminal.evaluacion.tipo_red else None) == (
        None if rechazada else red.value
    )
    assert terminal.version_solicitud == 2
    assert registro.instante <= evaluacion.instante <= terminal.instante
    escenario.bus.publicar(registro)
    escenario.bus.publicar(evaluacion)
    escenario.completar()
    assert escenario.reglas.confirmaciones == 1
    assert escenario.solicitudes.confirmaciones == 2
    assert len(escenario.bus.sin_suscriptores) == 1
    assert len(escenario.bus.publicados) == 5


@pytest.mark.parametrize("etapa", ["evaluar", "aplicar"])
def test_fallo_commit_no_deshace_pasos_previos_y_puede_reintentarse(etapa: str) -> None:
    escenario = Escenario()
    confirmacion = escenario.flujo.registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
    escenario.transferir()
    if etapa == "aplicar":
        escenario.bus.despachar_siguiente()
        escenario.transferir()
    almacen_fallido = escenario.reglas if etapa == "evaluar" else escenario.solicitudes
    almacen_fallido.fallar_confirmacion = True
    pendiente = escenario.bus.pendientes[0]
    with pytest.raises(RuntimeError, match="Fallo de confirmacion"):
        escenario.bus.despachar_siguiente()
    assert escenario.bus.pendientes[0] == pendiente
    solicitud = escenario.solicitudes.estado.solicitudes.obtener(confirmacion.id_solicitud)
    assert solicitud is not None and solicitud.version == 1
    assert len(escenario.reglas.estado.evaluaciones.evaluaciones) == (
        1 if etapa == "aplicar" else 0
    )
    assert almacen_fallido.estado.salidas == []
    almacen_fallido.fallar_confirmacion = False
    escenario.completar()
    solicitud = escenario.solicitudes.estado.solicitudes.obtener(confirmacion.id_solicitud)
    assert solicitud is not None and solicitud.version == 2
    assert escenario.reglas.confirmaciones == 1 and escenario.solicitudes.confirmaciones == 2


def test_politica_ausente_conserva_recepcion_y_recupera_con_la_misma_entrega() -> None:
    escenario = Escenario()
    escenario.reglas.estado.politicas.politicas.clear()
    confirmacion = escenario.flujo.registrar(
        RegistrarSolicitudPartner(datos=datos_solicitud(False))
    )
    escenario.transferir()
    with pytest.raises(ErrorConfiguracionPolitica):
        escenario.bus.despachar_siguiente()
    assert confirmacion.recepcion_confirmada
    assert escenario.solicitudes.confirmaciones == 1 and escenario.reglas.confirmaciones == 0
    escenario.reglas.estado.politicas.politicas[ID_PARTNER] = politica()
    escenario.completar()
    assert isinstance(escenario.bus.publicados[-1], SolicitudPartnerRechazada)


@pytest.mark.parametrize("observador_primero", [False, True])
def test_observador_independiente_no_cambia_flujo(observador_primero: bool) -> None:
    bus = BusEventosLocal()
    recibidos: list[SolicitudPartnerRegistrada] = []
    if observador_primero:
        bus.suscribir(SolicitudPartnerRegistrada, "observador", recibidos.append)
    escenario = Escenario(bus=bus)
    if not observador_primero:
        bus.suscribir(SolicitudPartnerRegistrada, "observador", recibidos.append)
    escenario.flujo.registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
    escenario.completar()
    assert len(recibidos) == 1
    assert isinstance(bus.publicados[-1], SolicitudPartnerListaParaAtencion)
    assert escenario.reglas.confirmaciones == 1 and escenario.solicitudes.confirmaciones == 2


def test_caida_despues_de_confirmar_reentrega_sin_reevaluar() -> None:
    escenario = Escenario()
    bus = BusEventosLocal()
    fallar = True

    def evaluar_y_fallar(evento: SolicitudPartnerRegistrada) -> None:
        escenario.flujo.evaluar(evento)
        if fallar:
            raise RuntimeError("Caida despues de commit")

    bus.suscribir(SolicitudPartnerRegistrada, "reglas", evaluar_y_fallar)
    escenario.flujo.registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
    escenario.solicitudes.transferir_salidas(bus)
    with pytest.raises(RuntimeError, match="despues de commit"):
        bus.despachar_siguiente()
    original = escenario.reglas.estado.salidas.copy()
    escenario.reglas.estado.politicas.politicas[ID_PARTNER] = replace(politica(), version=2)
    fallar = False
    bus.despachar_siguiente()
    assert escenario.reglas.confirmaciones == 1
    assert escenario.reglas.estado.salidas == original
    assert not bus.pendientes


def test_caida_despues_de_transicion_no_duplica_evento_terminal() -> None:
    escenario = Escenario()
    escenario.flujo.registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
    escenario.transferir()
    escenario.bus.despachar_siguiente()
    evaluacion = escenario.reglas.estado.salidas[0]
    assert isinstance(evaluacion, ReglasDePartnerEvaluadas)
    bus = BusEventosLocal()
    fallar = True

    def aplicar_y_fallar(evento: ReglasDePartnerEvaluadas) -> None:
        escenario.flujo.aplicar(evento)
        if fallar:
            raise RuntimeError("Caida despues de transicion")

    bus.suscribir(ReglasDePartnerEvaluadas, "solicitudes", aplicar_y_fallar)
    escenario.reglas.transferir_salidas(bus)
    with pytest.raises(RuntimeError, match="despues de transicion"):
        bus.despachar_siguiente()
    original = escenario.solicitudes.estado.salidas.copy()
    fallar = False
    bus.despachar_siguiente()
    assert escenario.solicitudes.confirmaciones == 2
    assert escenario.solicitudes.estado.salidas == original
    assert len(original) == 1


def test_reentrega_de_registro_antes_de_aplicar_conserva_evaluacion() -> None:
    escenario = Escenario()
    escenario.flujo.registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
    escenario.transferir()
    escenario.bus.despachar_siguiente()
    original = escenario.reglas.estado.salidas.copy()
    escenario.bus.publicar(escenario.bus.publicados[0])
    escenario.reglas.estado.politicas.politicas.clear()
    escenario.bus.despachar_siguiente()
    assert escenario.reglas.estado.salidas == original
    assert escenario.reglas.confirmaciones == 1
    escenario.completar()
    assert escenario.solicitudes.confirmaciones == 2
