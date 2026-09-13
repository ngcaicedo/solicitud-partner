from unittest.mock import Mock, patch

import pytest

from solicitudes_partner.config.serializacion import serializar_evento
from solicitudes_partner.modulos.solicitudes.infraestructura.consumidor_proyeccion import (
    ConsumidorProyeccion,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.mapeadores_eventos import (
    mensaje_lectura,
)
from tests.unitarias.dominio.datos import registro


def test_commit_antes_ack_y_fallo_conserva_mensaje() -> None:
    proyector = Mock()
    cliente = Mock()
    transporte = cliente.subscribe.return_value
    mensaje = transporte.receive.return_value
    mensaje.value.return_value = mensaje_lectura(serializar_evento(registro()))
    pasos: list[str] = []
    proyector.proyectar.side_effect = lambda _: pasos.append("commit")
    transporte.acknowledge.side_effect = lambda _: pasos.append("ack")
    consumidor = ConsumidorProyeccion(
        "pulsar://localhost:6650", "persistent://public/default/test", "test", proyector
    )
    with patch("pulsar.Client", return_value=cliente):
        assert consumidor.procesar_siguiente()
        assert pasos == ["commit", "ack"]
        proyector.proyectar.side_effect = RuntimeError("fallo")
        with pytest.raises(RuntimeError):
            consumidor.procesar_siguiente()
        assert transporte.acknowledge.call_count == 1
        transporte.negative_acknowledge.assert_called_once_with(mensaje)
        consumidor.cerrar()
        cliente.close.assert_called_once()


def test_error_de_suscripcion_cierra_cliente() -> None:
    cliente = Mock()
    cliente.subscribe.side_effect = RuntimeError("broker")
    consumidor = ConsumidorProyeccion(
        "pulsar://localhost:6650", "persistent://public/default/test", "test", Mock()
    )
    with patch("pulsar.Client", return_value=cliente):
        with pytest.raises(RuntimeError):
            consumidor.abrir()
    cliente.close.assert_called_once()
