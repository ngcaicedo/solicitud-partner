import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="partner-distribution-") as temporary_directory:
        temporary_path = Path(temporary_directory)
        environment_path = temporary_path / "environment"
        environment = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(environment_path)}
        subprocess.run(
            ["uv", "sync", "--locked", "--no-editable", "--no-dev"],
            cwd=project,
            env=environment,
            check=True,
        )
        subprocess.run(
            ["uv", "build", "--out-dir", str(temporary_path / "dist")],
            cwd=project,
            check=True,
        )
        wheel = next((temporary_path / "dist").glob("*.whl"))
        interpreter = environment_path / "bin" / "python"
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(interpreter),
                "--no-deps",
                "--reinstall",
                str(wheel),
            ],
            check=True,
        )
        verification = """
import sys
from pathlib import Path
import solicitudes_partner
from solicitudes_partner.modulos.solicitudes.dominio.entidades import SolicitudPartner
from solicitudes_partner.modulos.reglas_partner.dominio.servicios import evaluar_solicitud
from solicitudes_partner.seedwork.dominio.entidades import AgregacionRaiz
from solicitudes_partner.config.bootstrap import componer_flujo
from solicitudes_partner.seedwork.infraestructura.bus_eventos_local import BusEventosLocal
from solicitudes_partner.modulos.solicitudes.dominio.eventos import SolicitudPartnerRegistrada
from solicitudes_partner.modulos.reglas_partner.dominio.eventos import ReglasDePartnerEvaluadas
from solicitudes_partner.api.app import create_app
from solicitudes_partner.config.settings import Settings
from solicitudes_partner.config.persistencia import crear_uow_reglas, crear_uow_solicitudes
from solicitudes_partner.config.serializacion import decodificar_evento, serializar_evento
from solicitudes_partner.seedwork.infraestructura.outbox import RepositorioOutbox
from solicitudes_partner.seedwork.infraestructura.despacho_outbox import DespachadorOutbox

from solicitudes_partner.seedwork.infraestructura.publicador_pulsar import PublicadorPulsar
from solicitudes_partner.modulos.solicitudes.infraestructura.esquemas.v1.eventos import (
    SolicitudListaV1,
)
from pulsar.schema import AvroSchema
from solicitudes_partner.config.procesamiento import iniciar_despacho, iniciar_publicacion_cqrs
from solicitudes_partner.config.procesamiento import iniciar_proyeccion, procesar_eventos
from solicitudes_partner.modulos.solicitudes.infraestructura.esquemas.v1.lectura import (
    SolicitudLecturaV1,
)
from solicitudes_partner.modulos.solicitudes.infraestructura.repositorios import (
    RepositorioLecturaSQL,
)
assert AvroSchema(SolicitudLecturaV1) is not None
assert callable(iniciar_proyeccion) and callable(iniciar_publicacion_cqrs)
assert callable(RepositorioLecturaSQL)
assert callable(iniciar_despacho) and callable(procesar_eventos)
assert callable(PublicadorPulsar)
assert AvroSchema(SolicitudListaV1) is not None

package = Path(solicitudes_partner.__file__).resolve()
assert package.is_relative_to(Path(sys.prefix).resolve()), package
assert issubclass(SolicitudPartner, AgregacionRaiz)
assert callable(evaluar_solicitud)
assert callable(componer_flujo)
assert callable(crear_uow_reglas) and callable(crear_uow_solicitudes)
assert callable(decodificar_evento) and callable(serializar_evento)
assert callable(RepositorioOutbox) and callable(DespachadorOutbox)
assert SolicitudPartnerRegistrada.__module__.endswith(".dominio.eventos")
assert ReglasDePartnerEvaluadas.__module__.endswith(".dominio.eventos")
assert not BusEventosLocal().despachar_siguiente()
assert create_app(Settings()).title == "Entrada de Solicitudes de Partner"
print(f"Installed wheel imported outside source tree: {package}")
"""
        subprocess.run([str(interpreter), "-I", "-c", verification], cwd=temporary_path, check=True)


if __name__ == "__main__":
    main()
