from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA solicitudes")
    op.execute("CREATE SCHEMA reglas_partner")
    op.execute("CREATE SCHEMA mensajeria")
    op.execute("CREATE SCHEMA lectura")
    op.execute("""CREATE TABLE solicitudes.solicitudes (
        id UUID PRIMARY KEY, id_partner UUID NOT NULL, referencia_externa TEXT NOT NULL,
        datos JSONB NOT NULL, creada_en TIMESTAMPTZ NOT NULL, actualizada_en TIMESTAMPTZ NOT NULL,
        estado TEXT NOT NULL, version INTEGER NOT NULL, evaluacion JSONB,
        CONSTRAINT uq_solicitud_referencia UNIQUE (id_partner, referencia_externa),
        CONSTRAINT ck_solicitud_estado CHECK (
            (estado = 'RECIBIDA' AND version = 1 AND evaluacion IS NULL) OR
            (estado IN ('LISTA_PARA_ATENCION', 'RECHAZADA') AND version = 2
             AND evaluacion IS NOT NULL))
    )""")
    op.execute("""CREATE TABLE reglas_partner.politicas (
        id_partner UUID PRIMARY KEY, id UUID NOT NULL, version INTEGER NOT NULL,
        tipo_red TEXT NOT NULL, CONSTRAINT ck_politica_version CHECK (version > 0),
        CONSTRAINT ck_politica_red CHECK (tipo_red IN ('GENERAL_HDA', 'HOMOLOGADA_PARTNER'))
    )""")
    op.execute("""CREATE TABLE reglas_partner.evaluaciones (
        id UUID PRIMARY KEY, id_solicitud UUID NOT NULL, evento JSONB NOT NULL,
        CONSTRAINT uq_evaluacion_solicitud UNIQUE (id_solicitud)
    )""")
    op.execute("""CREATE TABLE reglas_partner.origenes (
        id_solicitud UUID PRIMARY KEY REFERENCES reglas_partner.evaluaciones(id_solicitud),
        registro JSONB NOT NULL
    )""")
    op.execute("""CREATE TABLE mensajeria.inbox (
        nombre_consumidor TEXT NOT NULL, id_evento UUID NOT NULL, documento JSONB NOT NULL,
        procesada_en TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (nombre_consumidor, id_evento)
    )""")
    op.execute("""CREATE TABLE mensajeria.outbox (
        id UUID PRIMARY KEY, id_evento UUID NOT NULL, destino TEXT NOT NULL,
        documento JSONB NOT NULL,
        creada_en TIMESTAMPTZ NOT NULL DEFAULT now(),
        proximo_intento TIMESTAMPTZ NOT NULL DEFAULT now(),
        enviada_en TIMESTAMPTZ, propietario TEXT, token UUID, vence_en TIMESTAMPTZ,
        intentos INTEGER NOT NULL DEFAULT 0, ultimo_error TEXT,
        CONSTRAINT uq_salida_destino UNIQUE (id_evento, destino)
    )""")
    op.execute(
        "CREATE INDEX ix_salida_pendiente ON mensajeria.outbox "
        "(enviada_en, proximo_intento, vence_en)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE mensajeria.outbox")
    op.execute("DROP TABLE mensajeria.inbox")
    op.execute("DROP TABLE reglas_partner.origenes")
    op.execute("DROP TABLE reglas_partner.evaluaciones")
    op.execute("DROP TABLE reglas_partner.politicas")
    op.execute("DROP TABLE solicitudes.solicitudes")
    op.execute("DROP SCHEMA lectura")
    op.execute("DROP SCHEMA mensajeria")
    op.execute("DROP SCHEMA reglas_partner")
    op.execute("DROP SCHEMA solicitudes")
