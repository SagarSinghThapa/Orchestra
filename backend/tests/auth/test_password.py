"""Unit tests for native bcrypt password hashing and verification."""

import pytest
from app.auth.password import hash_password, verify_password


def test_hash_password_success():
    """Verify that hashing a password returns a valid bcrypt hash distinct from plaintext."""
    raw_password = "SuperSecretPassword123!"
    hashed = hash_password(raw_password)

    assert hashed != raw_password
    assert hashed.startswith("$2b$")
    assert len(hashed) >= 59


def test_verify_password_correct():
    """Verify that a correct password matches its generated hash."""
    raw_password = "CorrectHorseBatteryStaple"
    hashed = hash_password(raw_password)

    assert verify_password(raw_password, hashed) is True


def test_verify_password_wrong():
    """Verify that an incorrect password fails verification."""
    raw_password = "OriginalPassword"
    hashed = hash_password(raw_password)

    assert verify_password("WrongPasswordGuess", hashed) is False
    assert verify_password("", hashed) is False


def test_hash_salting_uniqueness():
    """Verify that repeated hashing of the same password produces unique salted hashes."""
    password = "DeterministicInputDifferentSalt"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    assert hash1 != hash2
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True


def test_verify_password_invalid_hash():
    """Verify that malformed or invalid hashes return False without crashing."""
    assert verify_password("any_password", "not_a_valid_hash") is False
    assert verify_password("any_password", "") is False
    assert verify_password("any_password", "$2b$12$invalidtruncated") is False
