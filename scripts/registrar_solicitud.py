import argparse
import json
from uuid import UUID

from solicitudes_partner.config.database import create_database
from solicitudes_partner.config.persistencia import crear_uow_solicitudes
from solicitudes_partner.config.settings import Settings
from solicitudes_partner.modulos.solicitudes.aplicacion.comandos import RegistrarSolicitudPartner
from solicitudes_partner.modulos.solicitudes.aplicacion.handlers.registrar_solicitud import (
    RegistrarSolicitudHandler,
)
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
    DatosSolicitud,
    TipoSolicitud,
)
from solicitudes_partner.seedwork.infraestructura.identificadores import IdentificadoresAleatorios
from solicitudes_partner.seedwork.infraestructura.reloj import RelojActual


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Registrar una solicitud por el handler de aplicacion"
    )
    parser.add_argument("--id-partner", type=UUID, default=UUID(int=2))
    parser.add_argument("--referencia", required=True)
    parser.add_argument("--categoria", default="plomeria")
    parser.add_argument("--tipo", choices=list(TipoSolicitud), default=TipoSolicitud.SINIESTRO)
    parser.add_argument("--aprobacion", choices=("si", "no", "ausente"), default="si")
    argumentos = parser.parse_args()
    configuracion = Settings.from_environment()
    if not configuracion.database_url:
        parser.error("Definir PARTNER_DATABASE_URL")
    datos = DatosSolicitud(
        id_partner=argumentos.id_partner,
        referencia_externa=argumentos.referencia,
        categoria=argumentos.categoria,
        tipo=TipoSolicitud(argumentos.tipo),
        aprobacion_previa={"si": True, "no": False, "ausente": None}[argumentos.aprobacion],
    )
    base = create_database(configuracion.database_url)
    try:
        handler = RegistrarSolicitudHandler(
            lambda: crear_uow_solicitudes(base), RelojActual(), IdentificadoresAleatorios()
        )
        confirmacion = handler(RegistrarSolicitudPartner(datos=datos))
        print(
            json.dumps(
                {"id_solicitud": str(confirmacion.id_solicitud), "recepcion_confirmada": True}
            )
        )
    finally:
        base.close()


if __name__ == "__main__":
    main()
