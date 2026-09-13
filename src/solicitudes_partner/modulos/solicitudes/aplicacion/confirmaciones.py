from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ConfirmacionRegistroSolicitud:
    id_solicitud: UUID
    recepcion_confirmada: bool = True
