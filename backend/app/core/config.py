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

    # Authentication & Session Settings
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

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
    research_timeout_seconds: float = 45.0
    max_llm_calls_per_request: int = 3

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
            if self.llm_provider == "openai_compatible":
                if not self.llm_api_key:
                    raise RuntimeError(
                        "LLM_API_KEY must be configured for openai_compatible provider in production"
                    )
                if not self.llm_base_url or not (
                    self.llm_base_url.startswith("http://") or self.llm_base_url.startswith("https://")
                ):
                    raise RuntimeError(
                        "LLM_BASE_URL must begin with 'http://' or 'https://' in production"
                    )



settings = Settings()