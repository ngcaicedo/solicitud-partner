import logging
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event, Thread


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


def iniciar_ciclo(
    ejecutar_paso: Callable[[], object],
    nombre: str,
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
                    ejecutar_paso()
                except Exception as error:
                    logging.getLogger(__name__).exception("Fallo del procesamiento")
                    errores[:] = [error]
                detener.wait(pausa)
        finally:
            cerrar()

    hilo = Thread(target=ejecutar, name=nombre, daemon=False)
    procesamiento = Procesamiento(detener, hilo, errores)
    hilo.start()
    return procesamiento
