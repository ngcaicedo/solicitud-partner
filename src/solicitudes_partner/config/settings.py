import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = "solicitudes-partner"
    database_url: str | None = None
    pulsar_url: str = "pulsar://127.0.0.1:6650"
    topico_solicitudes: str = "persistent://public/default/solicitud-partner-lista-v1"

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            pulsar_url=os.environ.get("PARTNER_PULSAR_URL", "pulsar://127.0.0.1:6650"),
            topico_solicitudes=os.environ.get(
                "PARTNER_PULSAR_TOPIC", "persistent://public/default/solicitud-partner-lista-v1"
            ),
            service_name=os.environ.get("PARTNER_SERVICE_NAME", "solicitudes-partner"),
            database_url=os.environ.get("PARTNER_DATABASE_URL", "").strip() or None,
        )
