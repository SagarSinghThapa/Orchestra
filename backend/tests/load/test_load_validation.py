import pytest
from backend.tests.load.run_load import parse_duration_seconds, validate_load_parameters


def test_parse_duration_seconds():
    assert parse_duration_seconds("30s") == 30
    assert parse_duration_seconds("1m") == 60
    assert parse_duration_seconds("45") == 45


def test_validate_load_parameters_valid_boundaries():
    # Lower bounds
    assert validate_load_parameters(1, 1, "1s") == 1
    # Upper bounds
    assert validate_load_parameters(50, 10, "60s") == 60
    # Standard values
    assert validate_load_parameters(20, 5, "30s") == 30


def test_validate_load_parameters_rejects_excessive_users():
    with pytest.raises(ValueError, match="Invalid --users 51: must be between 1 and 50"):
        validate_load_parameters(51, 5, "30s")

    with pytest.raises(ValueError, match="Invalid --users 0: must be between 1 and 50"):
        validate_load_parameters(0, 5, "30s")


def test_validate_load_parameters_rejects_excessive_spawn_rate():
    with pytest.raises(ValueError, match="Invalid --spawn-rate 11: must be between 1 and 10"):
        validate_load_parameters(20, 11, "30s")

    with pytest.raises(ValueError, match="Invalid --spawn-rate 0: must be between 1 and 10"):
        validate_load_parameters(20, 0, "30s")


def test_validate_load_parameters_rejects_excessive_duration():
    with pytest.raises(ValueError, match="Invalid --duration 61s: duration must be between 1s and 60s"):
        validate_load_parameters(20, 5, "61s")

    with pytest.raises(ValueError, match="Invalid --duration 0s: duration must be between 1s and 60s"):
        validate_load_parameters(20, 5, "0s")


def test_validate_load_parameters_rejects_invalid_duration_format():
    with pytest.raises(ValueError, match="Invalid --duration format"):
        validate_load_parameters(20, 5, "invalid")

