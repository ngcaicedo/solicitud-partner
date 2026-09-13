import os
import subprocess
import sys


def test_import_and_lifespan_do_not_connect_to_infrastructure() -> None:
    script = """
import socket
from unittest.mock import patch

import psycopg

def forbidden_connection(*args, **kwargs):
    raise AssertionError("Unexpected external connection")

with (
    patch.object(socket.socket, "connect", forbidden_connection),
    patch.object(socket.socket, "connect_ex", forbidden_connection),
    patch.object(socket, "create_connection", forbidden_connection),
    patch.object(psycopg, "connect", forbidden_connection),
):
    from fastapi.testclient import TestClient
    from solicitudes_partner.config.persistencia import crear_uow_solicitudes
    from solicitudes_partner.seedwork.infraestructura.outbox import RepositorioOutbox
    from solicitudes_partner.api.app import create_app
    with TestClient(create_app()) as client:
        assert client.get("/health/live").status_code == 200
"""
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("PARTNER_", "PULSAR_", "PG")) and name != "DATABASE_URL"
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
