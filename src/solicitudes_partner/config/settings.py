import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = "solicitudes-partner"
    database_url: str | None = None
    pulsar_url: str = "pulsar://127.0.0.1:6650"
    topico_solicitudes: str = "persistent://public/default/solicitud-partner-lista-v1"

    topico_lectura: str = "persistent://public/default/solicitud-partner-lectura-v1"
    suscripcion_lectura: str = "solicitudes-lectura-v1"

    def __post_init__(self) -> None:
        if self.topico_lectura == self.topico_solicitudes:
            raise ValueError("CQRS requiere un topico independiente de integracion")
        if (
            not self.topico_lectura.startswith("persistent://")
            or not self.suscripcion_lectura.strip()
        ):
            raise ValueError("CQRS requiere topico persistente y suscripcion estable")

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            topico_lectura=os.environ.get(
                "PARTNER_CQRS_TOPIC", "persistent://public/default/solicitud-partner-lectura-v1"
            ),
            suscripcion_lectura=os.environ.get(
                "PARTNER_CQRS_SUBSCRIPTION", "solicitudes-lectura-v1"
            ),
            pulsar_url=os.environ.get("PARTNER_PULSAR_URL", "pulsar://127.0.0.1:6650"),
            topico_solicitudes=os.environ.get(
                "PARTNER_PULSAR_TOPIC", "persistent://public/default/solicitud-partner-lista-v1"
            ),
            service_name=os.environ.get("PARTNER_SERVICE_NAME", "solicitudes-partner"),
            database_url=os.environ.get("PARTNER_DATABASE_URL", "").strip() or None,
        )
