from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from solicitudes_partner.seedwork.infraestructura.orm import BaseSQL
from solicitudes_partner.seedwork.infraestructura.serializacion import Documento


class VistaSolicitudSQL(BaseSQL):
    __tablename__ = "solicitudes"
    __table_args__ = (
        Index("ix_lectura_partner_fecha", "id_partner", "creada_en", "id_solicitud"),
        {"schema": "lectura"},
    )
    id_solicitud: Mapped[UUID] = mapped_column(primary_key=True)
    id_partner: Mapped[UUID]
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version_solicitud: Mapped[int]
    documento: Mapped[Documento] = mapped_column(JSONB)
    proyectada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
