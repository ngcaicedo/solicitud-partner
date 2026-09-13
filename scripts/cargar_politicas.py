import argparse
import os
from uuid import UUID

from solicitudes_partner.config.database import create_database
from solicitudes_partner.config.persistencia import crear_uow_reglas
from solicitudes_partner.modulos.reglas_partner.dominio.objetos_valor import (
    PoliticaPartner,
    TipoRedProveedores,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar una politica de laboratorio")
    parser.add_argument("--id-partner", type=UUID, default=UUID(int=2))
    parser.add_argument("--id-politica", type=UUID, default=UUID(int=3))
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument(
        "--red", choices=list(TipoRedProveedores), default=TipoRedProveedores.GENERAL_HDA
    )
    argumentos = parser.parse_args()
    politica = PoliticaPartner(
        id=argumentos.id_politica,
        id_partner=argumentos.id_partner,
        version=argumentos.version,
        tipo_red=TipoRedProveedores(argumentos.red),
    )
    base = create_database(os.environ["PARTNER_DATABASE_URL"])
    try:
        with crear_uow_reglas(base) as unidad:
            unidad.politicas.guardar(politica)
            unidad.confirmar()
        print(
            f"Politica {politica.id} version {politica.version}: "
            f"partner {politica.id_partner}, {politica.tipo_red}"
        )
    finally:
        base.close()


if __name__ == "__main__":
    main()
