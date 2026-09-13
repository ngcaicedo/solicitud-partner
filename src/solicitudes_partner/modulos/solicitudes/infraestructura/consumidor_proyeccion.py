from typing import Any

from solicitudes_partner.modulos.solicitudes.infraestructura.proyecciones import (
    ProyectorSolicitudes,
)


class ConsumidorProyeccion:
    def __init__(
        self, url: str, topico: str, suscripcion: str, proyector: ProyectorSolicitudes
    ) -> None:
        if not topico.startswith("persistent://") or not suscripcion.strip():
            raise ValueError("Proyeccion requiere topico persistente y suscripcion")
        self.url = url
        self.topico = topico
        self.suscripcion = suscripcion
        self.proyector = proyector
        self._cliente: Any = None
        self._consumidor: Any = None

    def abrir(self) -> None:
        if self._consumidor is not None:
            return
        import pulsar
        from pulsar.schema import AvroSchema

        from solicitudes_partner.modulos.solicitudes.infraestructura.esquemas.v1.lectura import (
            SolicitudLecturaV1,
        )

        self._cliente = pulsar.Client(
            self.url, operation_timeout_seconds=5, connection_timeout_ms=5000
        )
        try:
            self._consumidor = self._cliente.subscribe(
                self.topico,
                self.suscripcion,
                schema=AvroSchema(SolicitudLecturaV1),
                initial_position=pulsar.InitialPosition.Earliest,
                consumer_type=pulsar.ConsumerType.Shared,
                receiver_queue_size=1,
                negative_ack_redelivery_delay_ms=1000,
            )
        except Exception:
            self.cerrar()
            raise

    def procesar_siguiente(self) -> bool:
        import pulsar

        from solicitudes_partner.modulos.solicitudes.infraestructura.mapeadores_eventos import (
            leer_mensaje,
        )

        self.abrir()
        try:
            mensaje = self._consumidor.receive(timeout_millis=500)
        except pulsar.Timeout:
            return False
        try:
            self.proyector.proyectar(leer_mensaje(mensaje.value()))
            self._consumidor.acknowledge(mensaje)
        except Exception:
            self._consumidor.negative_acknowledge(mensaje)
            raise
        return True

    def cerrar(self) -> None:
        cliente = self._cliente
        self._cliente = None
        self._consumidor = None
        if cliente is not None:
            cliente.close()
