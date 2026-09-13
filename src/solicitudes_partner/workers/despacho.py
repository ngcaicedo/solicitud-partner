import logging
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event, Thread
from typing import TYPE_CHECKING

from solicitudes_partner.config.bootstrap import componer_despacho_interno, componer_publicacion
from solicitudes_partner.config.persistencia import verificar_destinos

if TYPE_CHECKING:
    from solicitudes_partner.config.database import Database
    from solicitudes_partner.config.settings import Settings
    from solicitudes_partner.seedwork.infraestructura.despacho_outbox import DespachadorOutbox


@dataclass
class Procesamiento:
    detener_senal: Event
    hilo: Thread
    errores: list[Exception]

    def detener(self, timeout: float = 20) -> None:
        self.detener_senal.set()
        self.hilo.join(timeout)
        if self.hilo.is_alive():
            raise TimeoutError("El procesamiento no termino dentro del plazo")


def iniciar_despacho(
    despacho: "DespachadorOutbox",
    pausa: float = 0.2,
    cerrar: Callable[[], None] = lambda: None,
) -> Procesamiento:
    if pausa <= 0:
        raise ValueError("La pausa debe ser positiva")
    detener = Event()
    errores: list[Exception] = []

    def ejecutar() -> None:
        try:
            while not detener.is_set():
                try:
                    despacho.despachar_lote(1)
                except Exception as error:
                    logging.getLogger(__name__).exception("Fallo del ciclo de despacho")
                    errores[:] = [error]
                detener.wait(pausa)
        finally:
            cerrar()

    hilo = Thread(target=ejecutar, name=despacho.propietario, daemon=False)
    procesamiento = Procesamiento(detener, hilo, errores)
    hilo.start()
    return procesamiento


def iniciar_despacho_interno(base: "Database", pausa: float = 0.2) -> Procesamiento:
    verificar_destinos(base)
    return iniciar_despacho(componer_despacho_interno(base), pausa)


def iniciar_publicacion(base: "Database", configuracion: "Settings") -> Procesamiento:
    verificar_destinos(base)
    despacho, cerrar = componer_publicacion(base, configuracion)
    return iniciar_despacho(despacho, cerrar=cerrar)


def main() -> None:
    import argparse
    import signal

    from solicitudes_partner.config.database import create_database
    from solicitudes_partner.config.settings import Settings

    parser = argparse.ArgumentParser(description="Procesamiento de eventos de Entrada")
    parser.add_argument("modo", choices=("interno", "integracion"))
    argumentos = parser.parse_args()
    configuracion = Settings.from_environment()
    if not configuracion.database_url:
        parser.error("Definir PARTNER_DATABASE_URL")
    logging.basicConfig(level=logging.INFO)
    parada = Event()
    signal.signal(signal.SIGTERM, lambda *_: parada.set())
    signal.signal(signal.SIGINT, lambda *_: parada.set())
    base = create_database(configuracion.database_url)
    procesamiento = None
    try:
        procesamiento = (
            iniciar_despacho_interno(base)
            if argumentos.modo == "interno"
            else iniciar_publicacion(base, configuracion)
        )
        parada.wait()
    finally:
        if procesamiento is not None:
            procesamiento.detener()
        base.close()


if __name__ == "__main__":
    main()
