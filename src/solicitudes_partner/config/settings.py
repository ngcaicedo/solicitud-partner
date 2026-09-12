import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = "solicitudes-partner"
    database_url: str | None = None

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            service_name=os.environ.get("PARTNER_SERVICE_NAME", "solicitudes-partner"),
            database_url=os.environ.get("PARTNER_DATABASE_URL", "").strip() or None,
        )
