from unittest.mock import Mock, patch
from uuid import UUID, uuid4

import pytest

from solicitudes_partner.config.serializacion import decodificar_evento, serializar_evento
from solicitudes_partner.modulos.solicitudes.infraestructura.mapeadores_eventos import (
    evento_integracion,
)
from solicitudes_partner.seedwork.aplicacion.publicacion import Publicacion
from solicitudes_partner.seedwork.infraestructura.publicador_pulsar import PublicadorPulsar
from tests.contratos.test_solicitud_lista import terminal


def test_envio_espera_acuse_y_reutiliza_cliente() -> None:
    evento = terminal()
    salida = Publicacion(
        uuid4(), evento.id_evento, "integracion.solicitud_lista.v1", serializar_evento(evento)
    )
    with patch("pulsar.Client") as cliente:
        publicador = PublicadorPulsar(
            "pulsar://localhost:6650",
            "persistent://public/default/prueba",
            Mock(),
            lambda documento: evento_integracion(decodificar_evento(documento)),
        )
        cliente.assert_not_called()
        assert publicador.publicar(salida)
        assert publicador.publicar(salida)
        cliente.assert_called_once()
        productor = cliente.return_value.create_producer.return_value
        assert productor.send.call_count == 2
        assert productor.send.call_args.kwargs["partition_key"] == str(UUID(int=1))
        productor.send_async.assert_not_called()
        productor.send.side_effect = RuntimeError("broker caido")
        with pytest.raises(RuntimeError, match="broker caido"):
            publicador.publicar(salida)
        publicador.cerrar()
        cliente.return_value.close.assert_called_once()
