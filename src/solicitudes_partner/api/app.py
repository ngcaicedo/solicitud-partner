from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request

from solicitudes_partner.config.database import Database, create_database
from solicitudes_partner.config.settings import Settings


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def create_app(
    settings: Settings | None = None,
    database_factory: Callable[[str], Database] = create_database,
) -> FastAPI:
    configuration = settings if settings is not None else Settings.from_environment()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = (
            database_factory(configuration.database_url) if configuration.database_url else None
        )
        application.state.database = database
        try:
            yield
        finally:
            application.state.database = None
            if database is not None:
                database.close()

    application = FastAPI(title="Entrada de Solicitudes de Partner", lifespan=lifespan)
    application.state.settings = configuration
    application.state.database = None

    @application.get("/health/live", tags=["health"])
    def liveness(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    return application
