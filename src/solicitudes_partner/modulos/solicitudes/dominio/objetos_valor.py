from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from solicitudes_partner.seedwork.dominio.objetos_valor import ObjetoValor
from solicitudes_partner.seedwork.dominio.validaciones import validar_identidad, validar_texto


class TipoSolicitud(StrEnum):
    SINIESTRO = "SINIESTRO"
    INSTALACION = "INSTALACION"


class EstadoSolicitud(StrEnum):
    RECIBIDA = "RECIBIDA"
    LISTA_PARA_ATENCION = "LISTA_PARA_ATENCION"
    RECHAZADA = "RECHAZADA"


@dataclass(frozen=True, kw_only=True)
class DatosSolicitud(ObjetoValor):
    id_partner: UUID
    referencia_externa: str
    categoria: str
    tipo: TipoSolicitud
    aprobacion_previa: bool | None = None

    def __post_init__(self) -> None:
        validar_identidad(self.id_partner)
        validar_texto(self.referencia_externa)
        validar_texto(self.categoria)
        if not isinstance(self.tipo, TipoSolicitud):
            raise ValueError("Tipo de solicitud invalido")
        if self.aprobacion_previa is not None and type(self.aprobacion_previa) is not bool:
            raise ValueError("La aprobacion previa debe ser booleana")
        if self.tipo is TipoSolicitud.SINIESTRO and self.aprobacion_previa is None:
            raise ValueError("El siniestro requiere declarar aprobacion previa")
