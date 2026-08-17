from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import string
import time
from typing import Any

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


class InvalidSessionTokenError(ValueError):
    """Raised when a staff JWT is malformed, expired, or has an invalid signature."""


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise InvalidSessionTokenError("Invalid authentication token.") from exc


def generate_session_token(
    staff_id: str,
    role: str,
    secret_key: str,
    *,
    expires_in_seconds: int = 3600,
    issued_at: int | None = None,
) -> str:
    """Create a signed HS256 JWT for authenticating staff API requests."""
    issued_at = issued_at if issued_at is not None else int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": staff_id,
        "role": role,
        "iat": issued_at,
        "exp": issued_at + expires_in_seconds,
        "iss": "agile-clinic-portal",
    }
    segments = [
        _base64url_encode(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        for value in (header, payload)
    ]
    signing_input = ".".join(segments).encode("ascii")
    signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{segments[0]}.{segments[1]}.{_base64url_encode(signature)}"


def decode_session_token(
    token: str,
    secret_key: str,
    *,
    current_time: int | None = None,
) -> dict[str, Any]:
    """Validate and decode a staff JWT issued by :func:`generate_session_token`."""
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise InvalidSessionTokenError("Invalid authentication token.") from exc

    try:
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    except UnicodeEncodeError as exc:
        raise InvalidSessionTokenError("Invalid authentication token.") from exc
    expected_signature = hmac.new(
        secret_key.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    supplied_signature = _base64url_decode(encoded_signature)
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise InvalidSessionTokenError("Invalid authentication token.")

    try:
        header = json.loads(_base64url_decode(encoded_header))
        payload = json.loads(_base64url_decode(encoded_payload))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InvalidSessionTokenError("Invalid authentication token.") from exc

    if not isinstance(header, dict) or header != {"alg": "HS256", "typ": "JWT"}:
        raise InvalidSessionTokenError("Invalid authentication token.")
    if not isinstance(payload, dict):
        raise InvalidSessionTokenError("Invalid authentication token.")
    if payload.get("iss") != "agile-clinic-portal":
        raise InvalidSessionTokenError("Invalid authentication token.")
    if not isinstance(payload.get("sub"), str) or not isinstance(payload.get("role"), str):
        raise InvalidSessionTokenError("Invalid authentication token.")

    expiration = payload.get("exp")
    if not isinstance(expiration, int):
        raise InvalidSessionTokenError("Invalid authentication token.")
    now = current_time if current_time is not None else int(time.time())
    if expiration <= now:
        raise InvalidSessionTokenError("Authentication token has expired.")

    return payload
