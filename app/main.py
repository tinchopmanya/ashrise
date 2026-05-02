from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg import Error as PsycopgError
from psycopg import OperationalError

from app.config import get_settings
from app.routers.agent import router as agent_router
from app.routers.dashboard import router as dashboard_router
from app.routers.health import router as health_router
from app.routers.operations import router as operations_router
from app.routers.radar import router as radar_router
from app.routers.research import router as research_router
from app.routers.tasks import router as tasks_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.5.0")

    if settings.dashboard_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.dashboard_cors_origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(PsycopgError)
    def handle_psycopg_error(_, exc: PsycopgError):
        detail = getattr(getattr(exc, "diag", None), "message_primary", str(exc))
        status_code = 503 if isinstance(exc, OperationalError) else 400
        return JSONResponse(status_code=status_code, content={"detail": detail})

    app.include_router(health_router)
    app.include_router(operations_router)
    app.include_router(research_router)
    app.include_router(tasks_router)
    app.include_router(radar_router)
    app.include_router(dashboard_router)
    app.include_router(agent_router)

    return app


app = create_app()
