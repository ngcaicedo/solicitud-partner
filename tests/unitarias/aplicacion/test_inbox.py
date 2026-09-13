import pytest

from tests.unitarias.aplicacion.datos import Escenario
from tests.unitarias.aplicacion.dobles.unidad_trabajo import UnidadTrabajoReglasMemoria
from tests.unitarias.dominio.datos import registro


def test_inbox_confirma_con_evaluacion() -> None:
    escenario = Escenario()
    evento = registro()
    escenario.flujo.evaluar(evento)
    assert ("reglas_partner.evaluar", evento.id_evento) in escenario.reglas.estado.entradas


def test_inbox_revertido_y_consumidores_independientes() -> None:
    escenario = Escenario()
    evento = registro()
    with UnidadTrabajoReglasMemoria(escenario.reglas) as unidad:
        assert unidad.preparar_entrada("primero", evento)
    assert not escenario.reglas.estado.entradas
    with UnidadTrabajoReglasMemoria(escenario.reglas) as unidad:
        assert unidad.preparar_entrada("primero", evento)
        assert unidad.preparar_entrada("segundo", evento)
        unidad.confirmar()
    with UnidadTrabajoReglasMemoria(escenario.reglas) as unidad:
        assert not unidad.preparar_entrada("primero", evento)


def test_fallo_commit_no_deja_inbox() -> None:
    escenario = Escenario()
    escenario.reglas.fallar_confirmacion = True
    with pytest.raises(RuntimeError):
        escenario.flujo.evaluar(registro())
    assert not escenario.reglas.estado.entradas
