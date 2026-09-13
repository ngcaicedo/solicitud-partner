import argparse

import pulsar
from pulsar.schema import AvroSchema

from solicitudes_partner.config.settings import Settings
from solicitudes_partner.modulos.solicitudes.infraestructura.esquemas.v1.eventos import (
    SolicitudListaV1,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preparar topico y suscripciones de laboratorio")
    parser.add_argument("--suscripciones", nargs="+", default=["atencion", "estadisticas"])
    argumentos = parser.parse_args()
    configuracion = Settings.from_environment()
    cliente = pulsar.Client(
        configuracion.pulsar_url, operation_timeout_seconds=5, connection_timeout_ms=3000
    )
    try:
        productor = cliente.create_producer(
            configuracion.topico_solicitudes, schema=AvroSchema(SolicitudListaV1)
        )
        productor.close()
        for nombre in argumentos.suscripciones:
            consumidor = cliente.subscribe(
                configuracion.topico_solicitudes,
                nombre,
                initial_position=pulsar.InitialPosition.Earliest,
                consumer_type=pulsar.ConsumerType.Shared,
            )
            consumidor.close()
            print(f"Suscripcion disponible: {nombre}")
    finally:
        cliente.close()


if __name__ == "__main__":
    main()
