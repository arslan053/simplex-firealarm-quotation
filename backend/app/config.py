import os

from pydantic_settings import BaseSettings

_ENV = os.getenv("APP_ENV", "development")


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5435/ragm"
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 15
    APP_DOMAIN: str = "local"
    APP_PROTOCOL: str = "http"
    ADMIN_SUBDOMAIN: str = "admin"
    CORS_ORIGINS: str = "http://localhost:5175"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@app.com"
    SMTP_USE_TLS: bool = True
    EMAIL_BACKEND: str = "console"
    FRONTEND_URL: str = "http://localhost:5175"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_EXTERNAL_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "quotation-uploads"
    MINIO_USE_SSL: bool = False
    MINIO_EXTERNAL_USE_SSL: bool = False
    OPENAI_API_KEY: str = ""
    MOYASAR_SECRET_KEY: str = ""
    MOYASAR_WEBHOOK_SECRET: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": f".env.{_ENV}", "env_file_encoding": "utf-8"}


settings = Settings()
