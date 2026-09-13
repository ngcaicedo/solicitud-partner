from collections.abc import Callable
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from solicitudes_partner.modulos.solicitudes.aplicacion.vistas import VistaSolicitud
from solicitudes_partner.modulos.solicitudes.dominio.entidades import SolicitudPartner
from solicitudes_partner.modulos.solicitudes.infraestructura import mapeadores
from solicitudes_partner.modulos.solicitudes.infraestructura.mapeadores import (
    cargar_vista,
    guardar_vista,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.orm import SolicitudSQL
from solicitudes_partner.modulos.solicitudes.infraestructura.vistas import VistaSolicitudSQL
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


class RepositorioLecturaSQL:
    def __init__(self, crear_sesion: Callable[[], Session]) -> None:
        self.crear_sesion = crear_sesion

    def obtener(self, id_partner: UUID, id_solicitud: UUID) -> VistaSolicitud | None:
        with self.crear_sesion() as sesion:
            documento = sesion.scalar(
                select(VistaSolicitudSQL.documento).where(
                    VistaSolicitudSQL.id_partner == id_partner,
                    VistaSolicitudSQL.id_solicitud == id_solicitud,
                )
            )
            return cargar_vista(documento) if documento is not None else None

    def listar(self, id_partner: UUID, limite: int, desplazamiento: int) -> list[VistaSolicitud]:
        with self.crear_sesion() as sesion:
            documentos = sesion.scalars(
                select(VistaSolicitudSQL.documento)
                .where(VistaSolicitudSQL.id_partner == id_partner)
                .order_by(VistaSolicitudSQL.creada_en, VistaSolicitudSQL.id_solicitud)
                .limit(limite)
                .offset(desplazamiento)
            )
            return [cargar_vista(documento) for documento in documentos]


class RepositorioProyeccionSQL:
    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion

    def actualizar(self, vista: VistaSolicitud) -> bool:
        documento = guardar_vista(vista)
        insercion = insert(VistaSolicitudSQL).values(
            id_solicitud=vista.id_solicitud,
            id_partner=vista.id_partner,
            creada_en=vista.creada_en,
            version_solicitud=vista.version_solicitud,
            documento=documento,
        )
        actualizada = self.sesion.scalar(
            insercion.on_conflict_do_update(
                index_elements=[VistaSolicitudSQL.id_solicitud],
                set_=dict(
                    documento=insercion.excluded.documento,
                    version_solicitud=insercion.excluded.version_solicitud,
                    proyectada_en=func.clock_timestamp(),
                ),
                where=(VistaSolicitudSQL.version_solicitud < vista.version_solicitud)
                & (VistaSolicitudSQL.id_partner == vista.id_partner)
                & (VistaSolicitudSQL.creada_en == vista.creada_en),
            ).returning(VistaSolicitudSQL.id_solicitud)
        )
        if actualizada is not None:
            return True
        anterior = self.sesion.execute(
            select(
                VistaSolicitudSQL.id_partner,
                VistaSolicitudSQL.creada_en,
                VistaSolicitudSQL.version_solicitud,
                VistaSolicitudSQL.documento,
            ).where(VistaSolicitudSQL.id_solicitud == vista.id_solicitud)
        ).one()
        if (
            anterior.id_partner != vista.id_partner
            or anterior.creada_en != vista.creada_en
            or (
                anterior.version_solicitud == vista.version_solicitud
                and anterior.documento != documento
            )
        ):
            raise ValueError("Actualizacion contradictoria de la vista")
        return False
