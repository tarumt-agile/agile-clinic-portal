from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import string

_HASH_NAME = "sha256"
_ITERATIONS = 260_000
_SALT_BYTES = 16
_TEMP_PASSWORD_ALPHABET = string.ascii_letters + string.digits


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and a random salt. Returns "salt_hex$digest_hex"."""
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(_HASH_NAME, password.encode("utf-8"), salt, _ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Check a plaintext password against a hash produced by hash_password."""
    try:
        salt_hex, digest_hex = hashed.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False

    actual = hashlib.pbkdf2_hmac(_HASH_NAME, password.encode("utf-8"), salt, _ITERATIONS)
    return hmac.compare_digest(actual, expected)


def generate_temp_password(length: int = 12) -> str:
    """Generate a random temporary password for a newly created staff account."""
    return "".join(secrets.choice(_TEMP_PASSWORD_ALPHABET) for _ in range(length))
