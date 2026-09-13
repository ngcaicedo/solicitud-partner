from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from solicitudes_partner.api.solicitudes import router
from solicitudes_partner.config.database import Database, create_database
from solicitudes_partner.config.procesamiento import procesar_eventos
from solicitudes_partner.config.settings import Settings
from solicitudes_partner.seedwork.aplicacion.excepciones import ColisionPersistencia


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def create_app(
    settings: Settings | None = None,
    database_factory: Callable[[str], Database] = create_database,
    processing_factory: Callable[
        [Database, Settings], AbstractAsyncContextManager[None]
    ] = procesar_eventos,
) -> FastAPI:
    configuration = settings if settings is not None else Settings.from_environment()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = (
            database_factory(configuration.database_url) if configuration.database_url else None
        )
        application.state.database = database
        try:
            if database is None:
                yield
            else:
                async with processing_factory(database, configuration):
                    yield
        finally:
            application.state.database = None
            if database is not None:
                database.close()

    application = FastAPI(title="Entrada de Solicitudes de Partner", lifespan=lifespan)
    application.include_router(router)

    async def fallo_persistencia(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=503, content={"detail": "Persistencia temporalmente no disponible"}
        )

    application.add_exception_handler(SQLAlchemyError, fallo_persistencia)
    application.add_exception_handler(ColisionPersistencia, fallo_persistencia)
    application.state.settings = configuration
    application.state.database = None

    @application.get("/health/live", tags=["health"])
    def liveness(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    return application
