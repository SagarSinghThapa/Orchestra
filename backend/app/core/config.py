from typing import Any, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "meta/llama-3.1-70b-instruct",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-1.5-flash",
    },
}


class Settings(BaseSettings):
    database_url: Optional[str] = None
    jwt_secret: Optional[str] = None
    redis_url: Optional[str] = None
    environment: str = "production"
    app_git_sha: Optional[str] = None

    # Database Connection Pool Settings
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800

    # Authentication & Session Settings
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cors_allowed_origins: Union[list[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Storage & Document Ingestion Settings
    storage_local_root: str = "data/storage"
    max_upload_size_bytes: int = 10 * 1024 * 1024
    allowed_upload_extensions: tuple[str, ...] = (".pdf", ".txt", ".md")
    max_pdf_pages: int = 500

    # Embedding Provider Settings
    embedding_provider: str = "test"
    embedding_base_url: Optional[str] = None
    embedding_api_key: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    # Qdrant Vector Store Settings
    qdrant_url: Optional[str] = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection_name: str = "orchestra_knowledge"

    # Retrieval & Hybrid Search Settings
    retrieval_default_top_k: int = 5
    retrieval_max_top_k: int = 50
    retrieval_rrf_k: int = 60
    retrieval_dense_weight: float = 1.0
    retrieval_sparse_weight: float = 1.0
    retrieval_min_score_threshold: float = 0.0
    retrieval_max_project_chunks: int = 5000

    # LLM Provider & Research Agent Settings
    llm_provider: str = "test"
    llm_base_url: Optional[str] = "https://api.openai.com/v1"
    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 20.0
    llm_max_output_tokens: int = 2048
    llm_temperature: float = 0.0
    llm_max_retries: int = 2
    research_timeout_seconds: float = 45.0
    max_llm_calls_per_request: int = 3
    # Developer Subsystem Settings
    workspace_base_dir: str = "workspaces"

    # Rate Limiting Settings
    rate_limit_enabled: bool = True
    rate_limit_backend: str = "redis"  # "redis" or "memory"
    rate_limit_redis_fail_closed: bool = True
    rate_limit_auth_limit: int = 5
    rate_limit_auth_window_seconds: int = 60
    rate_limit_read_limit: int = 60
    rate_limit_read_window_seconds: int = 60
    rate_limit_ai_limit: int = 10
    rate_limit_ai_window_seconds: int = 60
    rate_limit_search_limit: int = 30
    rate_limit_search_window_seconds: int = 60
    rate_limit_upload_limit: int = 10
    rate_limit_upload_window_seconds: int = 60
    rate_limit_eval_limit: int = 5
    rate_limit_eval_window_seconds: int = 60
    trusted_proxies: list[str] = []

    # Observability & Metrics Settings
    metrics_enabled: bool = False
    otel_enabled: bool = False
    otel_service_name: str = "orchestra-backend"
    otel_sample_ratio: float = 0.1
    langsmith_tracing: bool = False

    @field_validator(
        "rate_limit_auth_limit",
        "rate_limit_read_limit",
        "rate_limit_ai_limit",
        "rate_limit_search_limit",
        "rate_limit_upload_limit",
        "rate_limit_eval_limit",
        "rate_limit_auth_window_seconds",
        "rate_limit_read_window_seconds",
        "rate_limit_ai_window_seconds",
        "rate_limit_search_window_seconds",
        "rate_limit_upload_window_seconds",
        "rate_limit_eval_window_seconds",
    )
    @classmethod
    def validate_positive_rate_limits(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Rate limit capacities and windows must be positive integers > 0")
        return v

    @field_validator("otel_sample_ratio")
    @classmethod
    def validate_sample_ratio(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("otel_sample_ratio must be between 0.0 and 1.0")
        return v

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, (list, tuple, set)):
            return list(v)
        return v

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

        if self.environment == "production":
            if self.embedding_provider == "test":
                raise RuntimeError(
                    "EMBEDDING_PROVIDER cannot be 'test' in production environment. "
                    "Configure a real provider such as 'openai_compatible' with required credentials."
                )
            if self.embedding_provider == "openai_compatible" and not self.embedding_api_key:
                raise RuntimeError(
                    "EMBEDDING_API_KEY must be configured for openai_compatible provider in production"
                )

            if self.llm_provider == "test":
                raise RuntimeError(
                    "LLM_PROVIDER cannot be 'test' in production environment. "
                    "Configure a real provider such as 'openai_compatible' with required credentials."
                )
            if self.llm_provider in ("openai_compatible", "openai", "groq", "nvidia", "gemini"):
                if not self.llm_api_key:
                    raise RuntimeError(
                        f"LLM_API_KEY must be configured for {self.llm_provider} provider in production"
                    )
                if self.llm_provider == "openai_compatible":
                    if not self.llm_base_url or not (
                        self.llm_base_url.startswith("http://") or self.llm_base_url.startswith("https://")
                    ):
                        raise RuntimeError(
                            "LLM_BASE_URL must begin with 'http://' or 'https://' in production"
                        )

            # Database Backend Guard (strict rejection of SQLite)
            db_url = (self.database_url or "").lower()
            if "sqlite" in db_url:
                raise RuntimeError(
                    "DATABASE_URL cannot use SQLite in production. PostgreSQL is required."
                )
            if not (db_url.startswith("postgresql://") or db_url.startswith("postgresql+psycopg://")):
                raise RuntimeError(
                    "DATABASE_URL must be a valid PostgreSQL connection URL in production."
                )

            # Rate Limiting Backend Guard
            if not self.rate_limit_enabled:
                raise RuntimeError("RATE_LIMIT_ENABLED must be True in production.")
            if self.rate_limit_backend != "redis":
                raise RuntimeError("RATE_LIMIT_BACKEND must be 'redis' in production.")

            # Qdrant Vector Store Guard
            q_url = (self.qdrant_url or "").strip().lower()
            if not q_url or q_url == ":memory:":
                raise RuntimeError("QDRANT_URL cannot be empty or ':memory:' in production.")
            if not (q_url.startswith("http://") or q_url.startswith("https://")):
                raise RuntimeError("QDRANT_URL must be a valid HTTP or HTTPS URL in production.")

            # JWT Secret Entropy & Default Rejection Guard
            weak_secrets = {
                "secret",
                "changeme",
                "your_jwt_secret_here",
                "your-jwt-secret-here",
                "test-jwt-secret-key-for-testing-only-12345",
            }
            if len(self.jwt_secret or "") < 32:
                raise RuntimeError("JWT_SECRET must be at least 32 characters long in production.")
            if (self.jwt_secret or "").strip() in weak_secrets or "default" in (self.jwt_secret or "").lower():
                raise RuntimeError("JWT_SECRET cannot use a known default or insecure value in production.")

            # CORS Security Guard
            for origin in self.cors_allowed_origins:
                if origin.strip() == "*":
                    raise RuntimeError("cors_allowed_origins cannot contain wildcard '*' in production.")



settings = Settings()