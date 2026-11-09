import pytest
from app.core.config import Settings


def _create_valid_prod_kwargs():
    return {
        "environment": "production",
        "database_url": "postgresql+psycopg://orchestra:secure_pass@localhost:5432/orchestra",
        "jwt_secret": "a-very-strong-production-jwt-secret-key-32chars!",
        "rate_limit_enabled": True,
        "rate_limit_backend": "redis",
        "qdrant_url": "http://localhost:6333",
        "llm_provider": "openai_compatible",
        "llm_api_key": "sk-real-production-api-key-here",
        "llm_base_url": "https://api.openai.com/v1",
        "embedding_provider": "openai_compatible",
        "embedding_api_key": "sk-real-embedding-api-key-here",
        "cors_allowed_origins": ["https://orchestra.example.com"],
    }


def test_production_config_valid_passes():
    """Verify that a fully compliant production configuration validates cleanly."""
    s = Settings(**_create_valid_prod_kwargs())
    s.validate_runtime_requirements()


def test_production_config_rejects_sqlite():
    """Verify that SQLite database URL is strictly rejected in production."""
    kwargs = _create_valid_prod_kwargs()
    kwargs["database_url"] = "sqlite:///orchestra.db"
    s = Settings(**kwargs)
    with pytest.raises(RuntimeError, match="DATABASE_URL cannot use SQLite in production"):
        s.validate_runtime_requirements()


def test_production_config_rejects_non_postgres():
    """Verify that non-PostgreSQL URLs are rejected in production."""
    kwargs = _create_valid_prod_kwargs()
    kwargs["database_url"] = "mysql://user:pass@localhost:3306/db"
    s = Settings(**kwargs)
    with pytest.raises(RuntimeError, match="DATABASE_URL must be a valid PostgreSQL connection URL"):
        s.validate_runtime_requirements()


def test_production_config_rejects_disabled_rate_limit():
    """Verify that disabling rate limiting is forbidden in production."""
    kwargs = _create_valid_prod_kwargs()
    kwargs["rate_limit_enabled"] = False
    s = Settings(**kwargs)
    with pytest.raises(RuntimeError, match="RATE_LIMIT_ENABLED must be True in production"):
        s.validate_runtime_requirements()


def test_production_config_rejects_memory_rate_limiter():
    """Verify that in-memory rate limiting backend is forbidden in production."""
    kwargs = _create_valid_prod_kwargs()
    kwargs["rate_limit_backend"] = "memory"
    s = Settings(**kwargs)
    with pytest.raises(RuntimeError, match="RATE_LIMIT_BACKEND must be 'redis' in production"):
        s.validate_runtime_requirements()


def test_production_config_rejects_in_memory_qdrant():
    """Verify that in-memory Qdrant (:memory:) is forbidden in production."""
    kwargs = _create_valid_prod_kwargs()
    kwargs["qdrant_url"] = ":memory:"
    s = Settings(**kwargs)
    with pytest.raises(RuntimeError, match="QDRANT_URL cannot be empty or ':memory:' in production"):
        s.validate_runtime_requirements()


def test_production_config_rejects_empty_qdrant():
    """Verify that empty Qdrant URL is forbidden in production."""
    kwargs = _create_valid_prod_kwargs()
    kwargs["qdrant_url"] = ""
    s = Settings(**kwargs)
    with pytest.raises(RuntimeError, match="QDRANT_URL cannot be empty or ':memory:' in production"):
        s.validate_runtime_requirements()


def test_production_config_rejects_short_jwt_secret():
    """Verify that JWT secret shorter than 32 characters is rejected in production."""
    kwargs = _create_valid_prod_kwargs()
    kwargs["jwt_secret"] = "too-short-secret"
    s = Settings(**kwargs)
    with pytest.raises(RuntimeError, match="JWT_SECRET must be at least 32 characters long"):
        s.validate_runtime_requirements()


def test_production_config_rejects_weak_default_jwt_secret():
    """Verify that known development default JWT secrets are rejected in production."""
    kwargs = _create_valid_prod_kwargs()
    kwargs["jwt_secret"] = "test-jwt-secret-key-for-testing-only-12345"
    s = Settings(**kwargs)
    with pytest.raises(RuntimeError, match="JWT_SECRET cannot use a known default or insecure value"):
        s.validate_runtime_requirements()


def test_production_config_rejects_wildcard_cors():
    """Verify that wildcard '*' CORS origin is forbidden in production."""
    kwargs = _create_valid_prod_kwargs()
    kwargs["cors_allowed_origins"] = ["*", "https://orchestra.example.com"]
    s = Settings(**kwargs)
    with pytest.raises(RuntimeError, match="cors_allowed_origins cannot contain wildcard"):
        s.validate_runtime_requirements()


def test_production_config_rejects_test_llm_provider():
    """Verify that test/mock LLM provider is rejected in production."""
    kwargs = _create_valid_prod_kwargs()
    kwargs["llm_provider"] = "test"
    s = Settings(**kwargs)
    with pytest.raises(RuntimeError, match="LLM_PROVIDER cannot be 'test' in production"):
        s.validate_runtime_requirements()


def test_production_config_rejects_test_embedding_provider():
    """Verify that test embedding provider is rejected in production."""
    kwargs = _create_valid_prod_kwargs()
    kwargs["embedding_provider"] = "test"
    s = Settings(**kwargs)
    with pytest.raises(RuntimeError, match="EMBEDDING_PROVIDER cannot be 'test' in production"):
        s.validate_runtime_requirements()
