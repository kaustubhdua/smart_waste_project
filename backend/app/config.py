"""Typed application configuration and production safety checks."""
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./smart_waste.db"
    api_token: str = "change-me-before-deployment"
    osrm_base_url: str = "https://router.project-osrm.org"
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080"
    auto_create_schema: bool = True
    seed_demo_data: bool = True
    telemetry_stale_after_minutes: int = 180
    telemetry_future_skew_seconds: int = 300
    model_path: str = "../models/waste_model.pkl"
    use_model_for_dispatch: bool = False


def validate_production_settings(config: Settings) -> None:
    """Fail closed on common unsafe production configuration mistakes.

    Development remains frictionless for local SQLite/tests. Production must
    explicitly configure durable storage, migrations, secrets, origins and
    demo-data policy rather than inheriting development defaults.
    """
    if config.app_env.strip().lower() != "production":
        return

    errors: list[str] = []
    if config.database_url.strip().lower().startswith("sqlite"):
        errors.append("DATABASE_URL must use a durable production database")
    if config.api_token.startswith(("change-me", "replace-with")) or len(config.api_token) < 32:
        errors.append("API_TOKEN must be a unique secret of at least 32 characters")
    if config.auto_create_schema:
        errors.append("AUTO_CREATE_SCHEMA must be false; use Alembic migrations")
    if config.seed_demo_data:
        errors.append("SEED_DEMO_DATA must be false in production")

    routing_url = urlparse(config.osrm_base_url.strip())
    if (
        routing_url.scheme != "https"
        or not routing_url.hostname
        or routing_url.username is not None
        or routing_url.password is not None
        or routing_url.query
        or routing_url.fragment
        or routing_url.hostname.lower() in {"router.project-osrm.org", "routing.openstreetmap.de"}
    ):
        errors.append(
            "OSRM_BASE_URL must be a trusted HTTPS routing provider; public demo routers are not production services"
        )

    origins = [origin.strip() for origin in config.cors_origins.split(",") if origin.strip()]
    if not origins or "*" in origins:
        errors.append("CORS_ORIGINS must explicitly list trusted HTTPS origins")
    else:
        for origin in origins:
            parsed = urlparse(origin)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in ("", "/")
                or parsed.params
                or parsed.query
                or parsed.fragment
                or parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
            ):
                errors.append(
                    "CORS_ORIGINS must contain only exact HTTPS origins (scheme, host and optional port; no credentials, path, query or fragment)"
                )
                break

    if errors:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))


settings = Settings()
validate_production_settings(settings)
