from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, StrictBool

from solicitudes_partner.config.bootstrap import (
    componer_consulta,
    componer_listado,
    componer_registro,
)
from solicitudes_partner.config.database import Database
from solicitudes_partner.modulos.solicitudes.aplicacion.comandos import RegistrarSolicitudPartner
from solicitudes_partner.modulos.solicitudes.aplicacion.confirmaciones import (
    ConfirmacionRegistroSolicitud,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.excepciones import ConflictoRegistro
from solicitudes_partner.modulos.solicitudes.aplicacion.handlers.consultar_solicitudes import (
    ConsultarSolicitudHandler,
    ListarSolicitudesHandler,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.handlers.registrar_solicitud import (
    RegistrarSolicitudHandler,
)
from solicitudes_partner.modulos.solicitudes.aplicacion.vistas import VistaSolicitud
from solicitudes_partner.modulos.solicitudes.dominio.objetos_valor import (
    DatosSolicitud,
    TipoSolicitud,
)

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])


class RegistroSolicitudHTTP(BaseModel):
    model_config = ConfigDict(extra="forbid")
    referencia_externa: str
    categoria: str
    tipo: TipoSolicitud
    aprobacion_previa: StrictBool | None = None


def obtener_partner_laboratorio(
    x_partner_laboratorio: Annotated[
        UUID,
        Header(description="Identidad seleccionada para la POC local; no autentica al cliente."),
    ],
) -> UUID:
    if x_partner_laboratorio.int == 0:
        raise HTTPException(422, "La identidad del partner debe ser un UUID no nulo")
    return x_partner_laboratorio


def obtener_base(request: Request) -> Database:
    base = cast(Database | None, request.app.state.database)
    if base is None:
        raise HTTPException(503, "Base de datos no configurada")
    return base


def obtener_registro(base: Annotated[Database, Depends(obtener_base)]) -> RegistrarSolicitudHandler:
    return componer_registro(base)


def obtener_consulta(base: Annotated[Database, Depends(obtener_base)]) -> ConsultarSolicitudHandler:
    return componer_consulta(base)


def obtener_listado(base: Annotated[Database, Depends(obtener_base)]) -> ListarSolicitudesHandler:
    return componer_listado(base)


@router.post(
    "",
    status_code=202,
    response_model=ConfirmacionRegistroSolicitud,
    responses={
        409: {"description": "Referencia con contenido distinto"},
        422: {"description": "Datos invalidos"},
        503: {"description": "Persistencia no disponible"},
    },
)
def registrar_solicitud(
    cuerpo: RegistroSolicitudHTTP,
    request: Request,
    response: Response,
    id_partner: Annotated[UUID, Depends(obtener_partner_laboratorio)],
    registrar: Annotated[RegistrarSolicitudHandler, Depends(obtener_registro)],
) -> ConfirmacionRegistroSolicitud:
    try:
        datos = DatosSolicitud(id_partner=id_partner, **cuerpo.model_dump())
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    try:
        confirmacion = registrar(RegistrarSolicitudPartner(datos=datos))
    except ConflictoRegistro as error:
        raise HTTPException(409, str(error)) from error
    response.headers["Location"] = str(
        request.url_for("consultar_solicitud", id_solicitud=confirmacion.id_solicitud)
    )
    return confirmacion


@router.get(
    "/{id_solicitud}",
    response_model=VistaSolicitud,
    responses={
        404: {"description": "No disponible en la vista; puede existir retraso de proyeccion"}
    },
)
def consultar_solicitud(
    id_solicitud: UUID,
    id_partner: Annotated[UUID, Depends(obtener_partner_laboratorio)],
    consultar: Annotated[ConsultarSolicitudHandler, Depends(obtener_consulta)],
) -> VistaSolicitud:
    vista = consultar(id_partner, id_solicitud)
    if vista is None:
        raise HTTPException(404, "no disponible en la vista")
    return vista


@router.get("", response_model=list[VistaSolicitud])
def listar_solicitudes(
    id_partner: Annotated[UUID, Depends(obtener_partner_laboratorio)],
    listar: Annotated[ListarSolicitudesHandler, Depends(obtener_listado)],
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
) -> list[VistaSolicitud]:
    return listar(id_partner, limite, desplazamiento)
