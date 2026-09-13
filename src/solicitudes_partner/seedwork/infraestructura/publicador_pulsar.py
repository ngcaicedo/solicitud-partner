from collections.abc import Callable
from typing import Any

from solicitudes_partner.seedwork.aplicacion.publicacion import Publicacion
from solicitudes_partner.seedwork.infraestructura.serializacion import Documento


class PublicadorPulsar:
    def __init__(
        self,
        url: str,
        topico: str,
        esquema: Any,
        convertir: Callable[[Documento], Any],
        timeout_segundos: int = 5,
    ) -> None:
        if timeout_segundos <= 0 or not topico.startswith("persistent://"):
            raise ValueError("Publicacion requiere timeout positivo y topico persistente")
        self.url = url
        self.topico = topico
        self.esquema = esquema
        self.convertir = convertir
        self.timeout_segundos = timeout_segundos
        self._cliente: Any = None
        self._productor: Any = None

    def publicar(self, publicacion: Publicacion) -> bool:
        mensaje = self.convertir(publicacion.documento)
        if str(publicacion.id_evento) != mensaje.event_id:
            raise ValueError("Identidad de entrega incompatible con evento publico")
        if self._productor is None:
            import pulsar

            self._cliente = pulsar.Client(
                self.url,
                operation_timeout_seconds=self.timeout_segundos,
                connection_timeout_ms=self.timeout_segundos * 1000,
            )
            try:
                self._productor = self._cliente.create_producer(
                    self.topico,
                    schema=self.esquema,
                    send_timeout_millis=self.timeout_segundos * 1000,
                    batching_enabled=False,
                    max_pending_messages=1,
                )
            except Exception:
                self.cerrar()
                raise
        self._productor.send(
            mensaje,
            partition_key=mensaje.id_solicitud,
            properties={"event_id": mensaje.event_id, "tipo": mensaje.tipo},
        )
        return True

    def cerrar(self) -> None:
        cliente = self._cliente
        self._cliente = None
        self._productor = None
        if cliente is not None:
            cliente.close()
