import pytest


@pytest.fixture
def sample_task_params():
    return {"depth": 3, "include_tests": True}
