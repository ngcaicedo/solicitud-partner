from solicitudes_partner.modulos.reglas_partner.dominio.eventos import ReglasDePartnerEvaluadas
from solicitudes_partner.modulos.reglas_partner.infraestructura import serializacion as reglas
from solicitudes_partner.modulos.solicitudes.infraestructura import serializacion as solicitudes
from solicitudes_partner.seedwork.dominio.eventos import EventoDominio
from solicitudes_partner.seedwork.infraestructura.serializacion import Documento


def serializar_evento(evento: EventoDominio) -> Documento:
    documento = (
        reglas.serializar(evento)
        if isinstance(evento, ReglasDePartnerEvaluadas)
        else solicitudes.serializar(evento)
    )
    decodificar_evento(documento)
    return documento


def decodificar_evento(documento: Documento) -> EventoDominio:
    try:
        if documento.get("tipo") == "ReglasDePartnerEvaluadas":
            return reglas.decodificar(documento)
        return solicitudes.decodificar(documento)
    except (KeyError, TypeError) as error:
        raise ValueError("Payload de evento invalido") from error
