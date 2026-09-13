import ast
import subprocess
import sys
from pathlib import Path


def test_importaciones_de_dominio_y_aplicacion_sin_infraestructura_ni_red() -> None:
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
    from solicitudes_partner.config.bootstrap import componer_flujo
    from solicitudes_partner.seedwork.infraestructura.bus_eventos_local import BusEventosLocal
"""
    proceso = subprocess.run(
        [sys.executable, "-I", "-c", codigo],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr


def test_fronteras_solo_permiten_eventos_y_tipos_de_mensaje_entre_modulos() -> None:
    raiz = Path(__file__).resolve().parents[3] / "src" / "solicitudes_partner"
    publicos = {
        "solicitudes": {
            "eventos": {
                "SolicitudPartnerRegistrada",
                "SolicitudPartnerListaParaAtencion",
                "SolicitudPartnerRechazada",
            },
            "objetos_valor": {"TipoSolicitud"},
        },
        "reglas_partner": {
            "eventos": {"ReglasDePartnerEvaluadas"},
            "objetos_valor": {"ResultadoEvaluacion", "TipoRedProveedores", "MotivoRechazo"},
        },
    }
    infracciones = []
    for archivo in raiz.rglob("*.py"):
        relativa = archivo.relative_to(raiz)
        es_dominio = "dominio" in relativa.parts
        if not es_dominio and "aplicacion" not in relativa.parts:
            continue
        modulo = relativa.parts[1] if relativa.parts[0] == "modulos" else None
        for nodo in ast.walk(ast.parse(archivo.read_text())):
            destinos: list[tuple[str, list[str]]] = []
            if isinstance(nodo, ast.Import):
                destinos = [(nombre.name, []) for nombre in nodo.names]
            elif isinstance(nodo, ast.ImportFrom):
                assert nodo.level == 0, f"Import relativo sin resolver: {archivo}"
                destinos = [(nodo.module or "", [nombre.name for nombre in nodo.names])]
            for destino, nombres in destinos:
                partes = destino.split(".")
                prohibidas = {"infraestructura", "api", "config"}
                if es_dominio:
                    prohibidas.add("aplicacion")
                if prohibidas.intersection(partes):
                    infracciones.append((str(relativa), destino))
                if destino.startswith("solicitudes_partner.modulos."):
                    propietario = partes[2]
                    if propietario == modulo:
                        continue
                    if es_dominio and modulo == "solicitudes":
                        infracciones.append((str(relativa), destino))
                        continue
                    permitidos = publicos.get(propietario, {})
                    if (
                        len(partes) != 5
                        or partes[3] != "dominio"
                        or not nombres
                        or not set(nombres).issubset(permitidos.get(partes[-1], set()))
                    ):
                        infracciones.append((str(relativa), destino))
    assert not infracciones


def test_dominio_solicitudes_se_importa_sin_reglas_partner() -> None:
    codigo = """
import importlib.abc
import sys

class BloquearReglas(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('solicitudes_partner.modulos.reglas_partner'):
            raise AssertionError(fullname)

sys.meta_path.insert(0, BloquearReglas())
from solicitudes_partner.modulos.solicitudes.dominio.entidades import SolicitudPartner
from solicitudes_partner.modulos.solicitudes.dominio.eventos import SolicitudPartnerRechazada
"""
    proceso = subprocess.run(
        [sys.executable, "-I", "-c", codigo],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
