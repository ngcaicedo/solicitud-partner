from dataclasses import dataclass

from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import DatosSolicitud


@dataclass(frozen=True, kw_only=True)
class RegistrarSolicitudPartner:
    datos: DatosSolicitud
