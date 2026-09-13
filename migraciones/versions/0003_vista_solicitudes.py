from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE lectura.solicitudes (
        id_solicitud UUID PRIMARY KEY, id_partner UUID NOT NULL,
        creada_en TIMESTAMPTZ NOT NULL, version_solicitud INTEGER NOT NULL,
        documento JSONB NOT NULL,
        proyectada_en TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
    )""")
    op.execute(
        "CREATE INDEX ix_lectura_partner_fecha ON lectura.solicitudes "
        "(id_partner, creada_en, id_solicitud)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE lectura.solicitudes")
