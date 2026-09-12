from typing import Protocol

from solicitudes_partner.modulos.solicitudes.dominio.entidades import SolicitudPartner
from solicitudes_partner.seedwork.dominio.repositorios import Repositorio


class RepositorioSolicitudes(Repositorio[SolicitudPartner], Protocol):
    pass
