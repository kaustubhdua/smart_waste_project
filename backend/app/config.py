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
    seed_demo_data: bool = False
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
    token = config.api_token
    if (
        token.lower().startswith(("change-me", "replace-with"))
        or len(token) < 32
        or not token.strip()
        or any(character.isspace() for character in token)
    ):
        errors.append("API_TOKEN must be a unique secret of at least 32 characters without whitespace or placeholder text")
    if config.auto_create_schema:
        errors.append("AUTO_CREATE_SCHEMA must be false; use Alembic migrations")
    if config.seed_demo_data:
        errors.append("SEED_DEMO_DATA must be false in production")

    routing_url = urlparse(config.osrm_base_url.strip())
    try:
        routing_port = routing_url.port
    except ValueError:
        routing_port = -1
    if (
        routing_url.scheme != "https"
        or not routing_url.hostname
        or routing_port == -1
        or routing_url.username is not None
        or routing_url.password is not None
        or routing_url.query
        or routing_url.fragment
        or any(character.isspace() for character in routing_url.netloc)
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
            try:
                origin_port = parsed.port
            except ValueError:
                origin_port = -1
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or origin_port == -1
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path != ""
                or parsed.params
                or parsed.query
                or parsed.fragment
                or any(character.isspace() for character in parsed.netloc)
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
