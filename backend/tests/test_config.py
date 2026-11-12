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
        "osrm_base_url": "https://routing.example.com",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_configuration_accepts_explicit_safe_settings():
    validate_production_settings(production_settings())


def test_production_configuration_accepts_authenticated_ors():
    validate_production_settings(production_settings(
        routing_provider="ors",
        ors_base_url="https://api.heigit.org/openrouteservice/v2",
        ors_api_key="test-managed-key",
    ))


@pytest.mark.parametrize("override", [
    {"routing_provider": "ors"},
    {"routing_provider": "ors", "ors_base_url": "https://api.openrouteservice.org/v2", "ors_api_key": "key"},
    {"routing_provider": "unknown"},
])
def test_production_configuration_rejects_untrusted_ors_settings(override):
    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        validate_production_settings(production_settings(**override))


@pytest.mark.parametrize(
    "override",
    [
        {"database_url": "sqlite:///./local.db"},
        {"api_token": "short"},
        {"api_token": "replace-with-a-long-random-operator-token"},
        {"api_token": "REPLACE-WITH-A-LONG-RANDOM-OPERATOR-TOKEN"},
        {"api_token": "a" * 24 + " " + "b" * 24},
        {"auto_create_schema": True},
        {"seed_demo_data": True},
        {"cors_origins": "*"},
        {"cors_origins": "http://ops.example.com"},
        {"cors_origins": "http://localhost:8080"},
        {"cors_origins": ""},
        {"cors_origins": "https://ops.example.com/admin"},
        {"cors_origins": "https://ops.example.com/"},
        {"cors_origins": "https://ops.example.com?next=drivers"},
        {"cors_origins": "https://user:pass@ops.example.com"},
        {"cors_origins": "https://ops.example.com#fragment"},
        {"cors_origins": "https://ops.example.com:notaport"},
        {"cors_origins": "https://ops .example.com"},
        {"osrm_base_url": "https://router.project-osrm.org"},
        {"osrm_base_url": "http://routing.example.com"},
        {"osrm_base_url": "https://user:pass@routing.example.com"},
        {"osrm_base_url": "https://routing.example.com?token=secret"},
        {"osrm_base_url": "https://routing.example.com:notaport"},
        {"osrm_base_url": "https://routing .example.com"},
    ],
)
def test_production_configuration_rejects_unsafe_settings(override):
    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        validate_production_settings(production_settings(**override))


def test_development_configuration_keeps_local_sqlite_defaults():
    config = Settings(app_env="development", database_url="sqlite:///./local.db")
    validate_production_settings(config)


def test_demo_data_is_opt_in_by_default(monkeypatch):
    monkeypatch.delenv("SEED_DEMO_DATA", raising=False)
    config = Settings(_env_file=None)
    assert config.seed_demo_data is False


def test_render_postgres_urls_select_psycopg_v3():
    from app.db import normalize_database_url

    assert normalize_database_url("postgresql://user:pass@host:5432/db") == "postgresql+psycopg://user:pass@host:5432/db"
    assert normalize_database_url("postgres://user:pass@host:5432/db") == "postgresql+psycopg://user:pass@host:5432/db"
    assert normalize_database_url("sqlite:///./local.db") == "sqlite:///./local.db"
