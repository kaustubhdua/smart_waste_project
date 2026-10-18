from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./smart_waste.db"
    api_token: str = "change-me-before-deployment"
    osrm_base_url: str = "https://router.project-osrm.org"
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080"
    auto_create_schema: bool = True
    telemetry_stale_after_minutes: int = 180
    telemetry_future_skew_seconds: int = 300
    model_path: str = "../models/waste_model.pkl"
    use_model_for_dispatch: bool = False

settings = Settings()
