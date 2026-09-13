import pytest
from sqlalchemy import delete, func, select

from solicitudes_partner.config.database import Database
from solicitudes_partner.config.persistencia import crear_uow_reglas, crear_uow_solicitudes
from solicitudes_partner.config.serializacion import decodificar_evento
from solicitudes_partner.modulos.reglas_partner.dominio.eventos import ReglasDePartnerEvaluadas
from solicitudes_partner.modulos.reglas_partner.dominio.excepciones import (
    ErrorConfiguracionPolitica,
)
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import TipoRedProveedores
from solicitudes_partner.modulos.reglas_partner.infraestructura.orm import (
    EvaluacionSQL,
    PoliticaSQL,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.comandos import RegistrarSolicitudPartner
from solicitudes_partner.modulos.solicitudes.dominio.eventos import SolicitudPartnerRegistrada
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
    EstadoSolicitud,
    TipoSolicitud,
)
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio
from solicitudes_partner.seedwork.infraestructura.inbox import EntradaSQL
from solicitudes_partner.seedwork.infraestructura.outbox import EventoSQL, SalidaSQL
from tests.integracion.datos import flujo_sql
from tests.unitarias.dominio.datos import datos_solicitud, politica


def evento_guardado(base: Database, tipo: str) -> EventoDominio:
    with base.session_factory() as sesion:
        documento = sesion.scalar(
            select(SalidaSQL.documento).where(SalidaSQL.documento["tipo"].astext == tipo)
        )
        assert documento is not None
        return decodificar_evento(documento)


@pytest.mark.parametrize("red", list(TipoRedProveedores))
@pytest.mark.parametrize(
    "tipo,aprobacion",
    [
        (TipoSolicitud.SINIESTRO, True),
        (TipoSolicitud.SINIESTRO, False),
        (TipoSolicitud.INSTALACION, None),
    ],
)
def test_recorrido_tres_transacciones_y_reinicio(
    base: Database, red: TipoRedProveedores, tipo: TipoSolicitud, aprobacion: bool | None
) -> None:
    with crear_uow_reglas(base) as unidad:
        unidad.politicas.guardar(politica(red))
        unidad.confirmar()
    flujo = flujo_sql(base)
    comando = RegistrarSolicitudPartner(datos=datos_solicitud(aprobacion, tipo))
    confirmacion = flujo.registrar(comando)
    with crear_uow_solicitudes(base) as unidad:
        recibida = unidad.solicitudes.obtener(confirmacion.id_solicitud)
        assert recibida is not None and recibida.estado is EstadoSolicitud.RECIBIDA
    registro = evento_guardado(base, "SolicitudPartnerRegistrada")
    assert isinstance(registro, SolicitudPartnerRegistrada)
    base.engine.dispose()
    flujo = flujo_sql(base)
    flujo.evaluar(registro)
    with crear_uow_solicitudes(base) as unidad:
        recibida = unidad.solicitudes.obtener(confirmacion.id_solicitud)
        assert recibida is not None and recibida.version == 1
    evaluacion = evento_guardado(base, "ReglasDePartnerEvaluadas")
    assert isinstance(evaluacion, ReglasDePartnerEvaluadas)
    with base.engine.begin() as conexion:
        conexion.execute(delete(PoliticaSQL))
    base.engine.dispose()
    flujo = flujo_sql(base)
    flujo.evaluar(registro)
    flujo.aplicar(evaluacion)
    flujo.aplicar(evaluacion)
    assert flujo.registrar(comando) == confirmacion
    with crear_uow_solicitudes(base) as unidad:
        final = unidad.solicitudes.obtener(confirmacion.id_solicitud)
        assert final is not None and final.version == 2
        assert final.evaluacion is not None
        assert final.evaluacion.id_evento == evaluacion.id_evento
        assert final.evaluacion.instante == evaluacion.instante
        assert final.retirar_eventos() == ()
        assert final.estado is (
            EstadoSolicitud.RECHAZADA
            if tipo is TipoSolicitud.SINIESTRO and aprobacion is False
            else EstadoSolicitud.LISTA_PARA_ATENCION
        )
    with base.session_factory() as sesion:
        assert sesion.scalar(select(func.count()).select_from(EventoSQL)) == 3
        assert sesion.scalar(select(func.count()).select_from(SalidaSQL)) == (
            4 if final.estado is EstadoSolicitud.RECHAZADA else 5
        )
        assert sesion.scalar(select(func.count()).select_from(EntradaSQL)) == 2
        assert sesion.scalar(select(func.count()).select_from(EvaluacionSQL)) == 1


def test_politica_ausente_permite_recuperar_sin_nuevo_registro(base: Database) -> None:
    flujo = flujo_sql(base)
    confirmacion = flujo.registrar(RegistrarSolicitudPartner(datos=datos_solicitud(False)))
    registro = evento_guardado(base, "SolicitudPartnerRegistrada")
    assert isinstance(registro, SolicitudPartnerRegistrada)
    with pytest.raises(ErrorConfiguracionPolitica):
        flujo.evaluar(registro)
    with base.session_factory() as sesion:
        assert sesion.scalar(select(func.count()).select_from(EntradaSQL)) == 0
        assert sesion.scalar(select(func.count()).select_from(EvaluacionSQL)) == 0
        assert sesion.scalar(select(func.count()).select_from(SalidaSQL)) == 2
    with crear_uow_reglas(base) as unidad:
        unidad.politicas.guardar(politica())
        unidad.confirmar()
    flujo.evaluar(registro)
    evaluacion = evento_guardado(base, "ReglasDePartnerEvaluadas")
    assert isinstance(evaluacion, ReglasDePartnerEvaluadas)
    flujo.aplicar(evaluacion)
    with crear_uow_solicitudes(base) as unidad:
        solicitud = unidad.solicitudes.obtener(confirmacion.id_solicitud)
        assert solicitud is not None and solicitud.estado is EstadoSolicitud.RECHAZADA


def test_flujo_cableado_con_outbox_y_bus_de_laboratorio(base: Database) -> None:
    from solicitudes_partner.config.bootstrap import componer_flujo_sql
    from solicitudes_partner.modulos.solicitudes.dominio.eventos import (
        SolicitudPartnerListaParaAtencion,
    )
    from solicitudes_partner.seedwork.aplicacion.publicacion import Publicacion
    from solicitudes_partner.seedwork.infraestructura.bus_eventos_local import BusEventosLocal
    from solicitudes_partner.seedwork.infraestructura.despacho_outbox import DespachadorOutbox
    from solicitudes_partner.seedwork.infraestructura.identificadores import (
        IdentificadoresAleatorios,
    )
    from solicitudes_partner.seedwork.infraestructura.outbox import RepositorioOutbox
    from solicitudes_partner.seedwork.infraestructura.reloj import RelojActual

    bus = BusEventosLocal()
    terminales: list[SolicitudPartnerListaParaAtencion] = []
    bus.suscribir(SolicitudPartnerListaParaAtencion, "observador", terminales.append)
    flujo = componer_flujo_sql(base, RelojActual(), IdentificadoresAleatorios(), bus)
    with crear_uow_reglas(base) as unidad:
        unidad.politicas.guardar(politica())
        unidad.confirmar()

    class TransporteLaboratorio:
        def publicar(self, publicacion: Publicacion) -> bool:
            bus.publicar(decodificar_evento(publicacion.documento))
            return True

    outbox = RepositorioOutbox(
        base.session_factory,
        ("reglas_partner.evaluar", "solicitudes.aplicar", "integracion.solicitud_lista.v1"),
    )
    despacho = DespachadorOutbox(outbox, TransporteLaboratorio(), "laboratorio")
    confirmacion = flujo.registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
    for _ in range(3):
        assert despacho.despachar_lote() == 1
        assert bus.despachar_siguiente()
    assert len(terminales) == 1 and terminales[0].id_solicitud == confirmacion.id_solicitud
    assert not bus.pendientes
    assert outbox.metricas()["pendientes"] == 2
    with crear_uow_solicitudes(base) as unidad_solicitudes:
        solicitud = unidad_solicitudes.solicitudes.obtener(confirmacion.id_solicitud)
        assert solicitud is not None and solicitud.version == 2
