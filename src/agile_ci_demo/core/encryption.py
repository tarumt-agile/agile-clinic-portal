"""AES-256-GCM encryption for PII columns stored at rest.

Applied at the data-access layer via EncryptedString, a SQLAlchemy column type
that encrypts on write and decrypts on read. Every layer above the ORM (service
functions, Pydantic schemas, routers) sees plain strings and needs no changes -
decryption only ever happens as a side effect of loading a row through the ORM,
which in this app always happens from inside an already-authenticated request
handler, since there is no code path that reads a Patient row outside of one.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from agile_ci_demo.core.config import settings

_NONCE_BYTES = 12


def _key() -> bytes:
    # AESGCM requires an exact 128/192/256-bit key. Deriving it from the
    # configured passphrase (rather than requiring the operator to generate
    # and format a raw key) keeps setup as simple as SECRET_KEY's.
    return hashlib.sha256(settings.patient_encryption_key.encode("utf-8")).digest()


def _deterministic_nonce_key() -> bytes:
    # A key distinct from the AES-GCM encryption key, so the same key material
    # is never used for two different cryptographic purposes (deriving a
    # nonce vs. encrypting data).
    return hashlib.sha256(_key() + b":deterministic-nonce").digest()


def _deterministic_nonce(plaintext: str) -> bytes:
    """A nonce derived from the plaintext itself via HMAC, so encrypting the
    same value twice always produces the same nonce (and therefore the same
    ciphertext) - see encrypt_deterministic() for why this tradeoff is made
    only for ic_or_passport."""
    digest = hmac.new(
        _deterministic_nonce_key(), plaintext.encode("utf-8"), hashlib.sha256
    ).digest()
    return digest[:_NONCE_BYTES]


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string for storage. Returns base64(nonce || ciphertext || tag)."""
    aesgcm = AESGCM(_key())
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def encrypt_deterministic(plaintext: str) -> str:
    """Encrypt a string so the same plaintext always produces the same stored
    value - unlike encrypt_value(), which uses a random nonce every time.

    This sacrifices semantic security (an attacker with the ciphertext can
    tell whether two values are equal) in exchange for being able to filter
    on the encrypted column directly in SQL (WHERE ic_or_passport == ...).
    That tradeoff is safe specifically for ic_or_passport because the column
    already carries a DB-level UNIQUE constraint - no two patients can ever
    share a value, so determinism can't reveal anything the app doesn't
    already guarantee (there are no duplicates to correlate). Do not reuse
    this for a column without an equivalent uniqueness guarantee.

    decrypt_value() reads this back exactly like encrypt_value()'s output -
    only how the nonce is derived differs, not the stored format.
    """
    aesgcm = AESGCM(_key())
    nonce = _deterministic_nonce(plaintext)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_value(stored: str) -> str:
    """Decrypt a value produced by encrypt_value."""
    raw = base64.b64decode(stored)
    nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    aesgcm = AESGCM(_key())
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


def is_encrypted(stored: str) -> bool:
    """Whether a stored value is already in encrypted form.

    Used only by the one-time migration that encrypts pre-existing plaintext
    rows, so it can be re-run safely without double-encrypting anything.
    Any failure decrypting (bad base64, auth tag mismatch, invalid UTF-8) means
    the value isn't ciphertext produced by encrypt_value - i.e. it's still
    plaintext and needs encrypting.
    """
    try:
        decrypt_value(stored)
        return True
    except Exception:
        return False


class EncryptedString(TypeDecorator):
    """A string column encrypted at rest with AES-256-GCM.

    Stored as Text (ciphertext is longer than the plaintext it replaces);
    application code still works with plain strings on either side.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return encrypt_value(value)

    def process_result_value(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return decrypt_value(value)


class DeterministicEncryptedString(TypeDecorator):
    """A string column encrypted at rest with AES-256-GCM, deterministically -
    see encrypt_deterministic() for the tradeoff this makes and why it's safe
    for ic_or_passport specifically. Because encrypting the same plaintext
    always yields the same stored value, SQLAlchemy comparisons against this
    column (e.g. `Patient.ic_or_passport == some_ic`) keep working exactly as
    they did before the column was encrypted - the comparison value is
    encrypted the same deterministic way when the query is built, so equal
    plaintexts still compare equal in SQL. Prefix/substring matching (LIKE)
    does not survive encryption, deterministic or not - see
    patients/service.py's search_patients_by_ic_prefix for how that's handled
    instead.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return encrypt_deterministic(value)

    def process_result_value(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return decrypt_value(value)
