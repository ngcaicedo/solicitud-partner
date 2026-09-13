from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from solicitudes_partner.seedwork.infraestructura.orm import BaseSQL
from solicitudes_partner.seedwork.infraestructura.serializacion import Documento


class SolicitudSQL(BaseSQL):
    __tablename__ = "solicitudes"
    __table_args__ = (
        UniqueConstraint("id_partner", "referencia_externa", name="uq_solicitud_referencia"),
        CheckConstraint(
            "(estado = 'RECIBIDA' AND version = 1 AND evaluacion IS NULL) OR "
            "(estado IN ('LISTA_PARA_ATENCION', 'RECHAZADA') AND version = 2 "
            "AND evaluacion IS NOT NULL)",
            name="ck_solicitud_estado",
        ),
        {"schema": "solicitudes"},
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    id_partner: Mapped[UUID]
    referencia_externa: Mapped[str]
    datos: Mapped[Documento] = mapped_column(JSONB)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actualizada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str]
    version: Mapped[int]
    evaluacion: Mapped[Documento | None] = mapped_column(JSONB(none_as_null=True))
