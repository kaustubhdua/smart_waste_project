import pytest

from app.config import Settings, validate_production_settings


def production_settings(**overrides):
    values = {
        "app_env": "production",
        "database_url": "postgresql+psycopg://app:password@db:5432/smartwaste",
        "api_token": "a" * 48,
        "cors_origins": "https://ops.example.com,https://drivers.example.com",
        "auto_create_schema": False,
        "seed_demo_data": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_configuration_accepts_explicit_safe_settings():
    validate_production_settings(production_settings())


@pytest.mark.parametrize(
    "override",
    [
        {"database_url": "sqlite:///./local.db"},
        {"api_token": "short"},
        {"api_token": "replace-with-a-long-random-operator-token"},
        {"auto_create_schema": True},
        {"seed_demo_data": True},
        {"cors_origins": "*"},
        {"cors_origins": "http://ops.example.com"},
        {"cors_origins": "http://localhost:8080"},
        {"cors_origins": ""},
    ],
)
def test_production_configuration_rejects_unsafe_settings(override):
    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        validate_production_settings(production_settings(**override))


def test_development_configuration_keeps_local_sqlite_defaults():
    config = Settings(app_env="development", database_url="sqlite:///./local.db")
    validate_production_settings(config)
