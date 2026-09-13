from solicitudes_partner.config.database import Database
from solicitudes_partner.config.persistencia import crear_uow_reglas, crear_uow_solicitudes
from solicitudes_partner.modulos.reglas_partner.dominio.entidades import EvaluacionReglasPartner
from tests.unitarias.dominio.datos import (
    ID_SOLICITUD,
    politica,
    registro,
    resultado,
    solicitud_nueva,
)


def test_solicitud_y_salida_persisten_en_otra_sesion(base: Database) -> None:
    original = solicitud_nueva()
    with crear_uow_solicitudes(base) as unidad:
        unidad.solicitudes.guardar(original)
        for evento in original.retirar_eventos():
            unidad.registrar_salida(evento)
        unidad.confirmar()
    base.engine.dispose()
    with crear_uow_solicitudes(base) as unidad:
        recuperada = unidad.solicitudes.obtener(ID_SOLICITUD)
        assert recuperada is not None
        assert recuperada.datos == original.datos
        assert recuperada.creada_en == original.creada_en
        assert recuperada.retirar_eventos() == ()


def test_evaluacion_origen_y_politica(base: Database) -> None:
    with crear_uow_reglas(base) as unidad:
        unidad.politicas.guardar(politica())
        unidad.evaluaciones.guardar(
            EvaluacionReglasPartner(id=resultado().id_evaluacion, evento=resultado())
        )
        unidad.evaluaciones.guardar_origen(registro())
        unidad.confirmar()
    with crear_uow_reglas(base) as unidad:
        evaluacion = unidad.evaluaciones.obtener_por_solicitud(ID_SOLICITUD)
        assert evaluacion is not None and evaluacion.evento == resultado()
        assert unidad.evaluaciones.obtener_origen(ID_SOLICITUD) == registro()
        assert unidad.politicas.obtener(politica().id_partner) == politica()


def test_referencia_igual_entre_partners_distintos(base: Database) -> None:
    from dataclasses import replace
    from uuid import uuid4

    from solicitudes_partner.modulos.solicitudes.aplicacion.comandos import (
        RegistrarSolicitudPartner,
    )
    from tests.integracion.datos import flujo_sql
    from tests.unitarias.dominio.datos import datos_solicitud

    flujo = flujo_sql(base)
    primera = flujo.registrar(RegistrarSolicitudPartner(datos=datos_solicitud()))
    segunda = flujo.registrar(
        RegistrarSolicitudPartner(datos=replace(datos_solicitud(), id_partner=uuid4()))
    )
    assert primera.id_solicitud != segunda.id_solicitud


def test_cambio_politica_no_modifica_evaluacion_y_origen_incompatible_falla(base: Database) -> None:
    from dataclasses import replace

    import pytest

    from solicitudes_partner.modulos.reglas_partner.aplicacion.excepciones import (
        ConflictoEvaluacion,
    )
    from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import TipoRedProveedores
    from tests.integracion.datos import flujo_sql

    with crear_uow_reglas(base) as unidad:
        unidad.politicas.guardar(politica())
        unidad.confirmar()
    flujo = flujo_sql(base)
    flujo.evaluar(registro())
    with crear_uow_reglas(base) as unidad:
        unidad.politicas.guardar(
            replace(politica(), version=2, tipo_red=TipoRedProveedores.HOMOLOGADA_PARTNER)
        )
        previa = unidad.evaluaciones.obtener_por_solicitud(ID_SOLICITUD)
        assert previa is not None
        unidad.confirmar()
    base.engine.dispose()
    flujo.evaluar(registro())
    with pytest.raises(ConflictoEvaluacion):
        flujo.evaluar(replace(registro(), datos=replace(registro().datos, categoria="otra")))
    with crear_uow_reglas(base) as unidad:
        posterior = unidad.evaluaciones.obtener_por_solicitud(ID_SOLICITUD)
        assert posterior is not None and posterior.evento == previa.evento
        assert posterior.evento.version_politica == 1


def test_proceso_nuevo_recupera_pendientes(base: Database) -> None:
    import os
    import subprocess
    import sys

    with crear_uow_solicitudes(base) as unidad:
        unidad.registrar_salida(registro())
        unidad.confirmar()
    codigo = """
import os
from sqlalchemy import select
from solicitudes_partner.config.database import create_database
from solicitudes_partner.config.serializacion import decodificar_evento
from solicitudes_partner.seedwork.infraestructura.outbox import SalidaSQL
base = create_database(os.environ['PARTNER_DATABASE_URL'])
try:
    with base.session_factory() as sesion:
        documento = sesion.scalar(select(SalidaSQL.documento))
        print(decodificar_evento(documento).id_evento)
finally:
    base.close()
"""
    proceso = subprocess.run(
        [sys.executable, "-I", "-c", codigo],
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "PARTNER_DATABASE_URL": base.engine.url.render_as_string(hide_password=False),
        },
        check=True,
        timeout=10,
    )
    assert proceso.stdout.strip() == str(registro().id_evento)
