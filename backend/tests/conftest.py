import pytest
from app.core.config import settings
from app.core.rate_limit import memory_limiter_storage


@pytest.fixture(autouse=True, scope="session")
def configure_global_test_environment():
    """Configures global test settings for deterministic, in-memory execution."""
    settings.environment = "test"
    settings.rate_limit_backend = "memory"
    settings.rate_limit_enabled = False


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    """Ensures each test function begins with empty rate limit buckets."""
    memory_limiter_storage.clear()
    yield
    memory_limiter_storage.clear()
