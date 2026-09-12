import ast
import subprocess
import sys
from pathlib import Path


def test_importaciones_de_dominio_y_contratos_sin_infraestructura_ni_red() -> None:
    codigo = """
import importlib.abc
import socket
import sys
from unittest.mock import patch

class BloquearInfraestructura(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'fastapi', 'sqlalchemy', 'pulsar', 'psycopg'}:
            raise AssertionError(fullname)

def prohibir_conexion(*args, **kwargs):
    raise AssertionError('Conexion externa inesperada')

sys.meta_path.insert(0, BloquearInfraestructura())
with patch.object(socket.socket, 'connect', prohibir_conexion):
    from solicitudes_partner.modulos.solicitudes.dominio.entidades import SolicitudPartner
    from solicitudes_partner.modulos.reglas_partner.dominio.servicios import evaluar_solicitud
    from solicitudes_partner.modulos.solicitudes.dominio.repositorios import RepositorioSolicitudes
    from solicitudes_partner.modulos.reglas_partner.dominio import repositorios
    from solicitudes_partner.seedwork.aplicacion.unidad_trabajo import UnidadTrabajo
"""
    proceso = subprocess.run(
        [sys.executable, "-I", "-c", codigo],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr


def test_fronteras_de_importacion_solo_permiten_contratos_entre_modulos() -> None:
    raiz = Path(__file__).resolve().parents[3] / "src" / "solicitudes_partner"
    infracciones = []
    for archivo in raiz.rglob("*.py"):
        relativa = archivo.relative_to(raiz)
        if "dominio" not in relativa.parts and archivo.name != "contratos.py":
            continue
        modulo = relativa.parts[1] if relativa.parts[0] == "modulos" else None
        arbol = ast.parse(archivo.read_text())
        for nodo in ast.walk(arbol):
            destinos: list[str] = []
            if isinstance(nodo, ast.Import):
                destinos = [nombre.name for nombre in nodo.names]
            elif isinstance(nodo, ast.ImportFrom):
                assert nodo.level == 0, f"Import relativo sin resolver: {archivo}"
                destinos = [nodo.module or ""]
            for destino in destinos:
                partes = destino.split(".")
                if any(
                    parte in partes for parte in ("infraestructura", "aplicacion", "api", "config")
                ):
                    infracciones.append((str(relativa), destino))
                if destino.startswith("solicitudes_partner.modulos."):
                    propietario = partes[2]
                    if (
                        propietario != modulo
                        and destino != f"solicitudes_partner.modulos.{propietario}.contratos"
                    ):
                        infracciones.append((str(relativa), destino))
    assert not infracciones
