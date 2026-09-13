from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, func, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from solicitudes_partner.seedwork.infraestructura.orm import BaseSQL
from solicitudes_partner.seedwork.infraestructura.serializacion import Documento


class EntradaSQL(BaseSQL):
    __tablename__ = "inbox"
    __table_args__ = {"schema": "mensajeria"}
    nombre_consumidor: Mapped[str] = mapped_column(primary_key=True)
    id_evento: Mapped[UUID] = mapped_column(primary_key=True)
    documento: Mapped[Documento] = mapped_column(JSONB)
    procesada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


def preparar(sesion: Session, consumidor: str, id_evento: UUID, documento: Documento) -> bool:
    if not consumidor.strip():
        raise ValueError("Consumidor vacio")
    nueva = sesion.scalar(
        insert(EntradaSQL)
        .values(nombre_consumidor=consumidor, id_evento=id_evento, documento=documento)
        .on_conflict_do_nothing(index_elements=[EntradaSQL.nombre_consumidor, EntradaSQL.id_evento])
        .returning(EntradaSQL.id_evento)
    )
    if nueva is not None:
        return True
    anterior = sesion.scalar(
        select(EntradaSQL.documento).where(
            EntradaSQL.nombre_consumidor == consumidor, EntradaSQL.id_evento == id_evento
        )
    )
    if anterior != documento:
        raise ValueError("La entrada ya tiene otro contenido")
    return False
