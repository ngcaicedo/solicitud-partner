from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from solicitudes_partner.seedwork.infraestructura.orm import BaseSQL
from solicitudes_partner.seedwork.infraestructura.serializacion import Documento


class PoliticaSQL(BaseSQL):
    __tablename__ = "politicas"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_politica_version"),
        CheckConstraint(
            "tipo_red IN ('GENERAL_HDA', 'HOMOLOGADA_PARTNER')", name="ck_politica_red"
        ),
        {"schema": "reglas_partner"},
    )
    id_partner: Mapped[UUID] = mapped_column(primary_key=True)
    id: Mapped[UUID]
    version: Mapped[int]
    tipo_red: Mapped[str]


class EvaluacionSQL(BaseSQL):
    __tablename__ = "evaluaciones"
    __table_args__ = (
        UniqueConstraint("id_solicitud", name="uq_evaluacion_solicitud"),
        {"schema": "reglas_partner"},
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    id_solicitud: Mapped[UUID]
    evento: Mapped[Documento] = mapped_column(JSONB)


class OrigenSQL(BaseSQL):
    __tablename__ = "origenes"
    __table_args__ = {"schema": "reglas_partner"}
    id_solicitud: Mapped[UUID] = mapped_column(
        ForeignKey("reglas_partner.evaluaciones.id_solicitud"), primary_key=True
    )
    registro: Mapped[Documento] = mapped_column(JSONB)
