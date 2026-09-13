import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import ExitStack, asynccontextmanager
from threading import Event
from typing import TYPE_CHECKING

from solicitudes_partner.config.bootstrap import (
    componer_despacho_interno,
    componer_proyeccion,
    componer_publicacion,
    componer_publicacion_cqrs,
)
from solicitudes_partner.config.persistencia import verificar_destinos
from solicitudes_partner.seedwork.infraestructura.ciclos import Procesamiento, iniciar_ciclo

if TYPE_CHECKING:
    from solicitudes_partner.config.database import Database
    from solicitudes_partner.config.settings import Settings
    from solicitudes_partner.seedwork.infraestructura.despacho_outbox import DespachadorOutbox


def iniciar_despacho(
    despacho: "DespachadorOutbox",
    pausa: float = 0.2,
    cerrar: Callable[[], None] = lambda: None,
) -> Procesamiento:
    return iniciar_ciclo(lambda: despacho.despachar_lote(1), despacho.propietario, pausa, cerrar)


def iniciar_despacho_interno(base: "Database", pausa: float = 0.2) -> Procesamiento:
    verificar_destinos(base)
    return iniciar_despacho(componer_despacho_interno(base), pausa)


def iniciar_publicacion(base: "Database", configuracion: "Settings") -> Procesamiento:
    verificar_destinos(base)
    despacho, cerrar = componer_publicacion(base, configuracion)
    return iniciar_despacho(despacho, cerrar=cerrar)


def iniciar_publicacion_cqrs(base: "Database", configuracion: "Settings") -> Procesamiento:
    verificar_destinos(base)
    despacho, cerrar = componer_publicacion_cqrs(base, configuracion)
    return iniciar_despacho(despacho, cerrar=cerrar)


def iniciar_proyeccion(base: "Database", configuracion: "Settings") -> Procesamiento:
    consumidor = componer_proyeccion(base, configuracion)
    return iniciar_ciclo(
        consumidor.procesar_siguiente, "proyeccion-solicitudes", cerrar=consumidor.cerrar
    )


@asynccontextmanager
async def procesar_eventos(base: "Database", configuracion: "Settings") -> AsyncIterator[None]:
    await asyncio.to_thread(verificar_destinos, base)
    suscripcion_preparada = Event()
    consumidor = componer_proyeccion(base, configuracion)
    despacho_cqrs, cerrar_cqrs = componer_publicacion_cqrs(base, configuracion)
    procesamientos: list[Procesamiento] = []
    cierres = ExitStack()

    def proyectar() -> None:
        consumidor.abrir()
        suscripcion_preparada.set()
        consumidor.procesar_siguiente()

    def publicar_lectura() -> None:
        if suscripcion_preparada.is_set():
            despacho_cqrs.despachar_lote(1)

    def agregar(procesamiento: Procesamiento) -> None:
        procesamientos.append(procesamiento)
        cierres.callback(procesamiento.detener)

    try:
        agregar(iniciar_despacho_interno(base))
        agregar(iniciar_publicacion(base, configuracion))
        agregar(iniciar_ciclo(proyectar, "proyeccion-solicitudes", cerrar=consumidor.cerrar))
        agregar(iniciar_ciclo(publicar_lectura, "publicacion-lectura", cerrar=cerrar_cqrs))
        yield
    finally:
        for procesamiento in procesamientos:
            procesamiento.detener_senal.set()
        await asyncio.to_thread(cierres.close)
