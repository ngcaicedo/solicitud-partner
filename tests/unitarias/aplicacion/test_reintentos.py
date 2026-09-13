import pytest

from solicitudes_partner.seedwork.aplicacion.excepciones import ColisionPersistencia
from solicitudes_partner.seedwork.aplicacion.reintentos import reintentar_colision


@pytest.mark.parametrize(
    "tipo_error,intentos_esperados", [(ColisionPersistencia, 3), (ValueError, 1)]
)
def test_reintento_acotado_y_solo_colisiones(
    tipo_error: type[Exception], intentos_esperados: int
) -> None:
    intentos = 0

    @reintentar_colision
    def fallar() -> None:
        nonlocal intentos
        intentos += 1
        raise tipo_error("Fallo")

    with pytest.raises(tipo_error):
        fallar()
    assert intentos == intentos_esperados
