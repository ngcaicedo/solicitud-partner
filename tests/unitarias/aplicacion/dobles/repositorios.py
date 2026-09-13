from dataclasses import dataclass, field
from uuid import UUID

from solicitudes_partner.modulos.reglas_partner.dominio.entidades import EvaluacionReglasPartner
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import PoliticaPartner
from solicitudes_partner.modulos.solicitudes.dominio.entidades import SolicitudPartner
from solicitudes_partner.modulos.solicitudes.dominio.eventos import (
    SolicitudPartnerRegistrada,
)


@dataclass
class RepositorioSolicitudesMemoria:
    solicitudes: dict[UUID, SolicitudPartner] = field(default_factory=dict)

    def obtener(self, id: UUID) -> SolicitudPartner | None:
        return self.solicitudes.get(id)

    def guardar(self, modelo: SolicitudPartner) -> None:
        self.solicitudes[modelo.id] = modelo

    def obtener_por_referencia(self, id_partner: UUID, referencia: str) -> SolicitudPartner | None:
        return next(
            (
                solicitud
                for solicitud in self.solicitudes.values()
                if solicitud.datos.id_partner == id_partner
                and solicitud.datos.referencia_externa == referencia
            ),
            None,
        )


@dataclass
class RepositorioEvaluacionesMemoria:
    evaluaciones: dict[UUID, EvaluacionReglasPartner] = field(default_factory=dict)
    origenes: dict[UUID, SolicitudPartnerRegistrada] = field(default_factory=dict)

    def obtener(self, id: UUID) -> EvaluacionReglasPartner | None:
        return self.evaluaciones.get(id)

    def guardar(self, modelo: EvaluacionReglasPartner) -> None:
        self.evaluaciones[modelo.id] = modelo

    def obtener_por_solicitud(self, id_solicitud: UUID) -> EvaluacionReglasPartner | None:
        return next(
            (
                evaluacion
                for evaluacion in self.evaluaciones.values()
                if evaluacion.evento.id_solicitud == id_solicitud
            ),
            None,
        )

    def obtener_origen(self, id_solicitud: UUID) -> SolicitudPartnerRegistrada | None:
        return self.origenes.get(id_solicitud)

    def guardar_origen(self, registro: SolicitudPartnerRegistrada) -> None:
        self.origenes[registro.id_solicitud] = registro


@dataclass
class RepositorioPoliticasMemoria:
    politicas: dict[UUID, PoliticaPartner] = field(default_factory=dict)
    consultas: int = 0

    def obtener(self, id_partner: UUID) -> PoliticaPartner | None:
        self.consultas += 1
        return self.politicas.get(id_partner)
