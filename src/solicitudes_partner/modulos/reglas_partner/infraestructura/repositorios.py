from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from solicitudes_partner.modulos.reglas_partner.dominio.entidades import EvaluacionReglasPartner
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import PoliticaPartner
from solicitudes_partner.modulos.reglas_partner.infraestructura.mapeadores import (
    cargar_evaluacion,
    cargar_politica,
)
from solicitudes_partner.modulos.reglas_partner.infraestructura.orm import (
    EvaluacionSQL,
    OrigenSQL,
    PoliticaSQL,
)
from solicitudes_partner.modulos.reglas_partner.infraestructura.serializacion import serializar
from solicitudes_partner.modulos.solicitudes.dominio.eventos import SolicitudPartnerRegistrada
from solicitudes_partner.modulos.solicitudes.infraestructura.serializacion import decodificar
from solicitudes_partner.modulos.solicitudes.infraestructura.serializacion import (
    serializar as serializar_registro,
)


class RepositorioEvaluacionesSQL:
    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion

    def obtener(self, id: UUID) -> EvaluacionReglasPartner | None:
        fila = self.sesion.get(EvaluacionSQL, id)
        return cargar_evaluacion(fila) if fila is not None else None

    def obtener_por_solicitud(self, id_solicitud: UUID) -> EvaluacionReglasPartner | None:
        fila = self.sesion.scalar(
            select(EvaluacionSQL).where(EvaluacionSQL.id_solicitud == id_solicitud)
        )
        return cargar_evaluacion(fila) if fila is not None else None

    def guardar(self, modelo: EvaluacionReglasPartner) -> None:
        modelo.__post_init__()
        self.sesion.add(
            EvaluacionSQL(
                id=modelo.id,
                id_solicitud=modelo.evento.id_solicitud,
                evento=serializar(modelo.evento),
            )
        )
        self.sesion.flush()

    def guardar_origen(self, registro: SolicitudPartnerRegistrada) -> None:
        self.sesion.add(
            OrigenSQL(id_solicitud=registro.id_solicitud, registro=serializar_registro(registro))
        )
        self.sesion.flush()

    def obtener_origen(self, id_solicitud: UUID) -> SolicitudPartnerRegistrada | None:
        fila = self.sesion.get(OrigenSQL, id_solicitud)
        if fila is None:
            return None
        evento = decodificar(fila.registro)
        if not isinstance(evento, SolicitudPartnerRegistrada):
            raise ValueError("Origen de evaluacion invalido")
        return evento


class RepositorioPoliticasSQL:
    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion

    def obtener(self, id_partner: UUID) -> PoliticaPartner | None:
        fila = self.sesion.get(PoliticaSQL, id_partner)
        return cargar_politica(fila) if fila is not None else None

    def guardar(self, politica: PoliticaPartner) -> None:
        politica.__post_init__()
        valores = dict(
            id=politica.id,
            id_partner=politica.id_partner,
            version=politica.version,
            tipo_red=politica.tipo_red.value,
        )
        self.sesion.execute(
            insert(PoliticaSQL)
            .values(**valores)
            .on_conflict_do_update(index_elements=[PoliticaSQL.id_partner], set_=valores)
        )
