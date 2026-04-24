from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class Settings:
    app_name: str
    database_url: str
    auth_token: str
    api_host: str
    api_port: int
    dashboard_cors_origins: tuple[str, ...]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    database_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("ASHRISE_DATABASE_URL")
        or "postgresql://postgres:postgres@localhost:5432/ashrise"
    )
    auth_token = os.getenv("ASHRISE_TOKEN") or "dev-token"

    return Settings(
        app_name="Ashrise Core",
        database_url=database_url,
        auth_token=auth_token,
        api_host=os.getenv("ASHRISE_API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("ASHRISE_API_PORT", "8080")),
        dashboard_cors_origins=tuple(
            origin
            for origin in (
                *(
                    item.strip()
                    for item in (os.getenv("ASHRISE_DASHBOARD_CORS_ORIGINS") or "").split(",")
                    if item.strip()
                ),
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:4173",
                "http://127.0.0.1:4173",
            )
            if origin
        ),
    )
