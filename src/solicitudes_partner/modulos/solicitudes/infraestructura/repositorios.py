from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from solicitudes_partner.modulos.solicitudes.dominio.entidades import SolicitudPartner
from solicitudes_partner.modulos.solicitudes.infraestructura import mapeadores
from solicitudes_partner.modulos.solicitudes.infraestructura.orm import SolicitudSQL
from solicitudes_partner.seedwork.aplicacion.excepciones import ColisionPersistencia


class RepositorioSolicitudesSQL:
    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion
        self.versiones: dict[UUID, int] = {}

    def _cargar(self, fila: SolicitudSQL | None) -> SolicitudPartner | None:
        if fila is None:
            return None
        self.versiones[fila.id] = fila.version
        return mapeadores.reconstruir(fila)

    def obtener(self, id: UUID) -> SolicitudPartner | None:
        return self._cargar(self.sesion.get(SolicitudSQL, id))

    def obtener_por_referencia(self, id_partner: UUID, referencia: str) -> SolicitudPartner | None:
        return self._cargar(
            self.sesion.scalar(
                select(SolicitudSQL).where(
                    SolicitudSQL.id_partner == id_partner,
                    SolicitudSQL.referencia_externa == referencia,
                )
            )
        )

    def guardar(self, modelo: SolicitudPartner) -> None:
        valores = mapeadores.valores(modelo)
        if modelo.id not in self.versiones:
            self.sesion.add(SolicitudSQL(**valores))
            self.sesion.flush()
        else:
            actualizado = self.sesion.scalar(
                update(SolicitudSQL)
                .where(
                    SolicitudSQL.id == modelo.id, SolicitudSQL.version == self.versiones[modelo.id]
                )
                .values(**valores)
                .returning(SolicitudSQL.id)
                .execution_options(synchronize_session=False)
            )
            if actualizado is None:
                raise ColisionPersistencia("La solicitud cambio desde su lectura")
            self.sesion.expire_all()
        self.versiones[modelo.id] = modelo.version
