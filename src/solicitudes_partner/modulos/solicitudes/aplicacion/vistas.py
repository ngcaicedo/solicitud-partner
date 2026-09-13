from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
    Admisibilidad,
    EstadoSolicitud,
    MotivoRechazo,
    TipoRedProveedores,
    TipoSolicitud,
)
from solicitudes_partner.seedwork.dominio.validaciones import (
    validar_identidad,
    validar_instante,
    validar_texto,
)


@dataclass(frozen=True, kw_only=True)
class VistaSolicitud:
    id_solicitud: UUID
    id_partner: UUID
    referencia_externa: str
    categoria: str
    tipo_solicitud: TipoSolicitud
    estado: EstadoSolicitud
    version_solicitud: int
    creada_en: datetime
    actualizada_en: datetime
    resultado: Admisibilidad | None = None
    motivo: MotivoRechazo | None = None
    tipo_red: TipoRedProveedores | None = None
    id_politica: UUID | None = None
    version_politica: int | None = None

    def __post_init__(self) -> None:
        validar_identidad(self.id_solicitud)
        validar_identidad(self.id_partner)
        validar_texto(self.referencia_externa)
        validar_texto(self.categoria)
        validar_instante(self.creada_en)
        validar_instante(self.actualizada_en)
        if self.actualizada_en < self.creada_en:
            raise ValueError("Fechas de vista invalidas")
        if not isinstance(self.tipo_solicitud, TipoSolicitud) or not isinstance(
            self.estado, EstadoSolicitud
        ):
            raise ValueError("Tipo o estado de vista invalido")
        if type(self.version_solicitud) is not int:
            raise ValueError("Version de vista invalida")
        if self.estado is EstadoSolicitud.RECIBIDA:
            if (
                self.version_solicitud != 1
                or any(
                    valor is not None
                    for valor in (
                        self.resultado,
                        self.motivo,
                        self.tipo_red,
                        self.id_politica,
                        self.version_politica,
                    )
                )
                or self.creada_en != self.actualizada_en
            ):
                raise ValueError("Vista recibida no puede tener evaluacion")
            return
        if (
            self.version_solicitud != 2
            or type(self.version_politica) is not int
            or self.version_politica < 1
        ):
            raise ValueError("Vista final requiere versiones validas")
        validar_identidad(self.id_politica)
        if self.estado is EstadoSolicitud.LISTA_PARA_ATENCION:
            if (
                self.resultado is not Admisibilidad.ADMISIBLE
                or not isinstance(self.tipo_red, TipoRedProveedores)
                or self.motivo is not None
            ):
                raise ValueError("Vista lista requiere red y no motivo")
        elif (
            self.resultado is not Admisibilidad.NO_ADMISIBLE
            or not isinstance(self.motivo, MotivoRechazo)
            or self.tipo_red is not None
        ):
            raise ValueError("Vista rechazada requiere motivo y no red")


@dataclass(frozen=True)
class ActualizacionVista:
    id_evento: UUID
    vista: VistaSolicitud

    def __post_init__(self) -> None:
        validar_identidad(self.id_evento)
        self.vista.__post_init__()
