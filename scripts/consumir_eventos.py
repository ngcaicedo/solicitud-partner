import argparse
import io
import json
import sqlite3
from pathlib import Path
from typing import Any

import fastavro
import pulsar


def persistir(datos: bytes, esquema: dict[str, Any], archivo: Path) -> str:
    mensaje = fastavro.schemaless_reader(io.BytesIO(datos), esquema)
    if not isinstance(mensaje, dict):
        raise ValueError("El mensaje debe ser un registro Avro")
    if (
        mensaje["tipo"] != "SolicitudDePartnerListaParaAtencion.v1"
        or mensaje["version_contrato"] != 1
    ):
        raise ValueError("Contrato no soportado")
    identidad = str(mensaje["event_id"])
    documento = json.dumps(mensaje, sort_keys=True)
    with sqlite3.connect(archivo) as conexion:
        conexion.execute(
            "CREATE TABLE IF NOT EXISTS recibidos "
            "(id_evento TEXT PRIMARY KEY, documento TEXT NOT NULL)"
        )
        anterior = conexion.execute(
            "SELECT documento FROM recibidos WHERE id_evento = ?", (identidad,)
        ).fetchone()
        if anterior is not None and anterior[0] != documento:
            raise ValueError("Evento repetido con contenido diferente")
        conexion.execute("INSERT OR IGNORE INTO recibidos VALUES (?, ?)", (identidad, documento))
    return identidad


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consumidor de laboratorio con persistencia propia"
    )
    parser.add_argument("--url", default="pulsar://127.0.0.1:6650")
    parser.add_argument(
        "--topico", default="persistent://public/default/solicitud-partner-lista-v1"
    )
    parser.add_argument("--suscripcion", required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument(
        "--esquema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs/contratos/solicitud-lista-v1.avsc",
    )
    parser.add_argument("--limite", type=int, default=1)
    parser.add_argument("--interrumpir-tras-commit", action="store_true")
    argumentos = parser.parse_args()
    esquema = json.loads(argumentos.esquema.read_text())
    cliente = pulsar.Client(argumentos.url, operation_timeout_seconds=5, connection_timeout_ms=3000)
    try:
        consumidor = cliente.subscribe(
            argumentos.topico,
            argumentos.suscripcion,
            consumer_type=pulsar.ConsumerType.Shared,
            initial_position=pulsar.InitialPosition.Earliest,
        )
        for _ in range(argumentos.limite):
            mensaje = consumidor.receive(timeout_millis=15000)
            identidad = persistir(mensaje.data(), esquema, argumentos.base)
            if argumentos.interrumpir_tras_commit:
                raise SystemExit(75)
            consumidor.acknowledge(mensaje)
            print(json.dumps({"event_id": identidad, "persistido": True}), flush=True)
    finally:
        cliente.close()


if __name__ == "__main__":
    main()
