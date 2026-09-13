from solicitudes_partner.modulos.solicitudes.dominio.entidades import SolicitudPartner
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import EstadoSolicitud
from solicitudes_partner.modulos.solicitudes.infraestructura.orm import SolicitudSQL
from solicitudes_partner.modulos.solicitudes.infraestructura.serializacion import (
    cargar_datos,
    cargar_resultado,
    guardar_datos,
    guardar_resultado,
)
from solicitudes_partner.seedwork.infraestructura.serializacion import Documento


def valores(solicitud: SolicitudPartner) -> Documento:
    solicitud.__post_init__()
    return dict(
        id=solicitud.id,
        id_partner=solicitud.datos.id_partner,
        referencia_externa=solicitud.datos.referencia_externa,
        datos=guardar_datos(solicitud.datos),
        creada_en=solicitud.creada_en,
        actualizada_en=solicitud.actualizada_en,
        estado=solicitud.estado.value,
        version=solicitud.version,
        evaluacion=guardar_resultado(solicitud.evaluacion) if solicitud.evaluacion else None,
    )


def reconstruir(fila: SolicitudSQL) -> SolicitudPartner:
    return SolicitudPartner.reconstruir(
        id=fila.id,
        datos=cargar_datos(fila.datos),
        creada_en=fila.creada_en,
        actualizada_en=fila.actualizada_en,
        estado=EstadoSolicitud(fila.estado),
        version=fila.version,
        evaluacion=cargar_resultado(fila.evaluacion) if fila.evaluacion is not None else None,
    )
