from dataclasses import dataclass
from datetime import datetime
from typing import Self
from uuid import UUID

from solicitudes_partner.modulos.solicitudes.dominio.eventos import (
    SolicitudPartnerListaParaAtencion,
    SolicitudPartnerRechazada,
    SolicitudPartnerRegistrada,
    validar_evaluacion_solicitud,
)
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
    Admisibilidad,
    DatosSolicitud,
    EstadoSolicitud,
    ResultadoEvaluacion,
)
from solicitudes_partner.seedwork.dominio.entidades import AgregacionRaiz
from solicitudes_partner.seedwork.dominio.validaciones import validar_instante, validar_version


@dataclass(frozen=True, eq=False, kw_only=True)
class SolicitudPartner(AgregacionRaiz):
    datos: DatosSolicitud
    creada_en: datetime
    actualizada_en: datetime
    estado: EstadoSolicitud
    version: int
    evaluacion: ResultadoEvaluacion | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        validar_instante(self.creada_en)
        validar_instante(self.actualizada_en)
        validar_version(self.version)
        if not isinstance(self.datos, DatosSolicitud) or not isinstance(
            self.estado, EstadoSolicitud
        ):
            raise ValueError("Datos o estado de solicitud invalidos")
        if self.estado is EstadoSolicitud.RECIBIDA:
            if (
                self.version != 1
                or self.evaluacion is not None
                or self.actualizada_en != self.creada_en
            ):
                raise ValueError("Una solicitud recibida requiere version 1 y ninguna evaluacion")
        else:
            if self.version != 2 or self.evaluacion is None:
                raise ValueError("Una solicitud finalizada requiere version 2 y una evaluacion")
            validar_evaluacion_solicitud(
                self.evaluacion, self.id, self.datos, self.creada_en, self.actualizada_en
            )
            estado_esperado = (
                EstadoSolicitud.LISTA_PARA_ATENCION
                if self.evaluacion.resultado is Admisibilidad.ADMISIBLE
                else EstadoSolicitud.RECHAZADA
            )
            if self.estado is not estado_esperado:
                raise ValueError("El estado no corresponde al resultado de evaluacion")

    @classmethod
    def registrar(
        cls, *, id: UUID, datos: DatosSolicitud, id_evento: UUID, instante: datetime
    ) -> Self:
        solicitud = cls(
            id=id,
            datos=datos,
            creada_en=instante,
            actualizada_en=instante,
            estado=EstadoSolicitud.RECIBIDA,
            version=1,
        )
        solicitud._registrar_evento(
            SolicitudPartnerRegistrada(
                id_evento=id_evento,
                instante=instante,
                id_solicitud=id,
                datos=datos,
            )
        )
        return solicitud

    @classmethod
    def reconstruir(
        cls,
        *,
        id: UUID,
        datos: DatosSolicitud,
        creada_en: datetime,
        actualizada_en: datetime,
        estado: EstadoSolicitud,
        version: int,
        evaluacion: ResultadoEvaluacion | None,
    ) -> Self:
        return cls(
            id=id,
            datos=datos,
            creada_en=creada_en,
            actualizada_en=actualizada_en,
            estado=estado,
            version=version,
            evaluacion=evaluacion,
        )

    def aplicar_resultado_evaluacion(
        self,
        evaluacion: ResultadoEvaluacion,
        *,
        id_evento: UUID,
        instante: datetime,
    ) -> None:
        if self.evaluacion is not None:
            if evaluacion == self.evaluacion:
                return
            raise ValueError("La solicitud ya tiene una evaluacion inicial")
        validar_instante(instante)
        validar_evaluacion_solicitud(evaluacion, self.id, self.datos, self.creada_en, instante)
        clase_evento = (
            SolicitudPartnerListaParaAtencion
            if evaluacion.resultado is Admisibilidad.ADMISIBLE
            else SolicitudPartnerRechazada
        )
        evento = clase_evento(
            id_evento=id_evento,
            instante=instante,
            id_solicitud=self.id,
            datos=self.datos,
            creada_en=self.creada_en,
            evaluacion=evaluacion,
        )
        object.__setattr__(self, "estado", evento.estado)
        object.__setattr__(self, "version", 2)
        object.__setattr__(self, "evaluacion", evaluacion)
        object.__setattr__(self, "actualizada_en", instante)
        self._registrar_evento(evento)
