from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from solicitudes_partner.config.database import Database
from solicitudes_partner.config.persistencia import metadata


def test_migracion_crea_esquemas_y_coincide_con_orm(base: Database) -> None:
    assert {"solicitudes", "reglas_partner", "mensajeria", "lectura"}.issubset(
        inspect(base.engine).get_schema_names()
    )
    with base.engine.connect() as conexion:
        assert conexion.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
        contexto = MigrationContext.configure(conexion, opts={"include_schemas": True})
        assert compare_metadata(contexto, metadata) == []
