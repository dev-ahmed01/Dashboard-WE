from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./test_local.db"
    jwt_secret: str = ""
    cors_origin: str = "http://localhost:5173"
    public_site_url: str = "https://workspacebyemlen.co.in"
    admin_email: str = ""
    admin_password: str = ""
    admin_username: str = ""  # Optional admin login alias, opt-in via local environment
    s3_endpoint_url: str = "http://minio:9000"
    s3_public_url: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "workspace-assets"
    max_upload_bytes: int = 8 * 1024 * 1024
    app_environment: str = "development"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache

def get_settings():
    return Settings()
