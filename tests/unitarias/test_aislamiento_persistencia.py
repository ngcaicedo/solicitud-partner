import subprocess
import sys


def test_repositorios_sql_no_importan_pulsar() -> None:
    codigo = """
import importlib.abc
import sys

class BloquearPulsar(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'pulsar' or fullname.startswith('pulsar.'):
            raise AssertionError(fullname)

sys.meta_path.insert(0, BloquearPulsar())
from solicitudes_partner.config.persistencia import crear_uow_solicitudes, crear_uow_reglas
"""
    resultado = subprocess.run(
        [sys.executable, "-I", "-c", codigo], capture_output=True, text=True, timeout=10
    )
    assert resultado.returncode == 0, resultado.stderr
