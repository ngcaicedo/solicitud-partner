from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE mensajeria.eventos (
        id_evento UUID PRIMARY KEY, documento JSONB NOT NULL
    )""")
    op.execute("""INSERT INTO mensajeria.eventos (id_evento, documento)
        SELECT DISTINCT ON (id_evento) id_evento, documento
        FROM mensajeria.outbox ORDER BY id_evento, creada_en, id
    """)


def downgrade() -> None:
    op.execute("DROP TABLE mensajeria.eventos")
