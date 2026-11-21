import bcrypt


def hash_password(password: str) -> str:
    """Hash a plaintext password using native bcrypt with automatic salt generation."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash in constant time."""
    pwd_bytes = password.encode("utf-8")
    hash_bytes = password_hash.encode("utf-8")
    try:
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except (ValueError, TypeError):
        return False