from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: Optional[str] = None
    jwt_secret: Optional[str] = None
    redis_url: Optional[str] = None
    environment: str = "production"

    # Database Connection Pool Settings
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def validate_runtime_requirements(self) -> None:
        """
        Enforces that production-required settings are provided via environment configuration.
        Fails fast with clear descriptive error when mandatory configuration is missing.
        """
        missing = []
        if not self.database_url:
            missing.append("DATABASE_URL")
        if not self.jwt_secret:
            missing.append("JWT_SECRET")
        if missing:
            raise RuntimeError(
                f"Missing required environment configuration: {', '.join(missing)}. "
                "Define these variables in your environment or .env file before running Orchestra."
            )


settings = Settings()