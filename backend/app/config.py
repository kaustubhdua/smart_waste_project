from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./smart_waste.db"
    api_token: str = "change-me-before-deployment"
    device_token: str = "change-me-device-token"
    osrm_base_url: str = "https://router.project-osrm.org"
    require_road_routing: bool = True

settings = Settings()
