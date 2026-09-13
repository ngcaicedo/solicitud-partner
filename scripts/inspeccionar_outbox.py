import json
import os

from solicitudes_partner.config.database import create_database
from solicitudes_partner.seedwork.infraestructura.outbox import RepositorioOutbox


def main() -> None:
    base = create_database(os.environ["PARTNER_DATABASE_URL"])
    try:
        outbox = RepositorioOutbox(base.session_factory)
        print(
            json.dumps(
                dict(metricas=outbox.metricas(), pendientes=outbox.inspeccionar()),
                default=str,
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        base.close()


if __name__ == "__main__":
    main()
