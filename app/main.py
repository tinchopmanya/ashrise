from fastapi import FastAPI
from fastapi.responses import JSONResponse
from psycopg import Error as PsycopgError
from psycopg import OperationalError

from app.config import get_settings
from app.routers.agent import router as agent_router
from app.routers.health import router as health_router
from app.routers.operations import router as operations_router
from app.routers.research import router as research_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.4.0")

    @app.exception_handler(PsycopgError)
    def handle_psycopg_error(_, exc: PsycopgError):
        detail = getattr(getattr(exc, "diag", None), "message_primary", str(exc))
        status_code = 503 if isinstance(exc, OperationalError) else 400
        return JSONResponse(status_code=status_code, content={"detail": detail})

    app.include_router(health_router)
    app.include_router(operations_router)
    app.include_router(research_router)
    app.include_router(agent_router)

    return app


app = create_app()
