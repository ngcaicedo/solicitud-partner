from solicitudes_partner.modulos.reglas_partner.aplicacion.handlers.evaluar_registro import (
    EvaluarRegistroHandler,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.handlers.aplicar_resultado import (
    AplicarResultadoEvaluacionHandler,
)
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio

DESTINOS_INTERNOS = (
    EvaluarRegistroHandler.consumidor,
    AplicarResultadoEvaluacionHandler.consumidor,
)
DESTINOS_EXTERNOS = ("integracion.solicitud_lista.v1",)
DESTINOS_ADMITIDOS = DESTINOS_INTERNOS + DESTINOS_EXTERNOS


def destinos_evento(evento: EventoDominio) -> tuple[str, ...]:
    rutas = {
        "SolicitudPartnerRegistrada": (EvaluarRegistroHandler.consumidor,),
        "ReglasDePartnerEvaluadas": (AplicarResultadoEvaluacionHandler.consumidor,),
        "SolicitudPartnerListaParaAtencion": DESTINOS_EXTERNOS,
        "SolicitudPartnerRechazada": (),
    }
    try:
        return rutas[type(evento).__name__]
    except KeyError as error:
        raise ValueError("Evento sin ruta definida") from error
