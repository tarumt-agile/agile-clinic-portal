from __future__ import annotations

import datetime as dt
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agile_ci_demo.app import app
from agile_ci_demo.core.database import Base, encrypt_legacy_patient_pii, get_db
from agile_ci_demo.core.encryption import (
    decrypt_value,
    encrypt_deterministic,
    encrypt_value,
    is_encrypted,
)
from agile_ci_demo.patients import models as _patients_models  # noqa: F401

# --- 1. Core encryption module (no DB/client needed) ---------------------------


def test_encrypt_value_uses_a_random_nonce_each_time() -> None:
    """Two encryptions of the same plaintext must not produce the same stored
    value - semantic security depends on this for phone/email/address."""
    first = encrypt_value("012-3456789")
    second = encrypt_value("012-3456789")
    assert first != second


def test_encrypt_value_round_trips() -> None:
    assert decrypt_value(encrypt_value("jane.tan@example.com")) == "jane.tan@example.com"


def test_encrypt_deterministic_is_stable_across_calls() -> None:
    """The whole point of the deterministic variant: encrypting the same IC
    twice must produce the exact same stored value, so SQL equality on the
    encrypted column still finds it."""
    first = encrypt_deterministic("900520-10-1234")
    second = encrypt_deterministic("900520-10-1234")
    assert first == second


def test_encrypt_deterministic_differs_for_different_plaintexts() -> None:
    a = encrypt_deterministic("900520-10-1234")
    b = encrypt_deterministic("900520-10-1236")
    assert a != b


def test_encrypt_deterministic_round_trips() -> None:
    assert decrypt_value(encrypt_deterministic("A1234567")) == "A1234567"


def test_is_encrypted_detects_ciphertext_and_rejects_plaintext() -> None:
    assert is_encrypted(encrypt_value("some value")) is True
    assert is_encrypted(encrypt_deterministic("some value")) is True
    assert is_encrypted("900520-10-1234") is False
    assert is_encrypted("not base64 at all!!") is False


# --- 2. Isolated in-memory DB per test ------------------------------------------


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI test client backed by a fresh in-memory SQLite DB for every test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)


def valid_patient_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "full_name": "Jane Tan",
        "date_of_birth": "1990-05-20",
        "gender": "female",
        "phone_number": "012-3456789",
        "email": "jane.tan@example.com",
        "ic_or_passport": "900520-10-1234",
        "address": "1 Jalan Testing, Kuala Lumpur",
    }
    payload.update(overrides)
    return payload


def _raw_patient_row(client: TestClient, patient_id: int = 1) -> object:
    """Read a patient row straight off the SQLite connection - text() queries
    bypass the ORM's column type entirely, so this sees exactly what's on
    disk, not what EncryptedString/DeterministicEncryptedString decrypts it to."""
    db = next(app.dependency_overrides[get_db]())
    try:
        return db.execute(
            text(
                "SELECT phone_number, email, address, ic_or_passport "
                "FROM patients WHERE id = :id"
            ),
            {"id": patient_id},
        ).one()
    finally:
        db.close()


# --- 3. PII is actually encrypted at rest ---------------------------------------


def test_patient_pii_is_not_stored_as_plaintext(client: TestClient) -> None:
    """Every encrypted PII field must be unreadable directly off disk - this is
    the whole point of the encryption story, so it's asserted directly against
    the raw row rather than just trusting the API round-trips correctly."""
    r = client.post("/api/patients", json=valid_patient_payload())
    assert r.status_code == 201

    row = _raw_patient_row(client)
    assert row.phone_number != "012-3456789"
    assert row.email != "jane.tan@example.com"
    assert row.address != "1 Jalan Testing, Kuala Lumpur"
    assert row.ic_or_passport != "900520-10-1234"

    # And each raw value really is ciphertext this app produced, not just
    # some other string that happens to differ from the input.
    assert is_encrypted(row.phone_number)
    assert is_encrypted(row.email)
    assert is_encrypted(row.address)
    assert is_encrypted(row.ic_or_passport)


def test_patient_pii_round_trips_through_the_api_despite_encryption(client: TestClient) -> None:
    """The encryption is transparent - the API must still return the original
    plaintext even though it's encrypted on disk."""
    created = client.post("/api/patients", json=valid_patient_payload()).json()

    r = client.get(f"/api/patients/{created['patient_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["phone_number"] == "012-3456789"
    assert body["email"] == "jane.tan@example.com"
    assert body["address"] == "1 Jalan Testing, Kuala Lumpur"
    assert body["ic_or_passport"] == "900520-10-1234"


# --- 4. Exact-match IC lookup still works despite deterministic encryption -----


def test_lookup_by_ic_finds_the_patient_despite_encryption(client: TestClient) -> None:
    """GET /api/patients/by-ic/{ic} relies on `WHERE ic_or_passport == :value` -
    this is the transparency deterministic encryption is specifically for:
    the comparison value gets encrypted the same deterministic way when the
    query runs, so it still matches the encrypted stored value."""
    client.post("/api/patients", json=valid_patient_payload())

    r = client.get("/api/patients/by-ic/900520-10-1234")
    assert r.status_code == 200
    assert r.json()["full_name"] == "Jane Tan"


def test_lookup_by_ic_unknown_value_returns_404(client: TestClient) -> None:
    r = client.get("/api/patients/by-ic/900520-10-9999")
    assert r.status_code == 404


def test_patient_login_still_works_with_encrypted_ic(client: TestClient) -> None:
    """Patient login authenticates by IC/passport (see auth/service.py's
    authenticate_patient) - the same exact-match path as by-ic lookup."""
    created = client.post("/api/patients", json=valid_patient_payload()).json()

    r = client.post(
        "/api/auth/patient-login",
        json={"ic_or_passport": "900520-10-1234", "phone_number": created["phone_number"]},
    )
    assert r.status_code == 200


# --- 5. Legacy-data migration ----------------------------------------------------


def _use_test_engine_for_legacy_migration(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """encrypt_legacy_patient_pii() runs against core.database's module-level
    `engine`, not the get_db-overridden session this test's client actually
    uses - without repointing it here, the migration would run against
    whatever real database core.database.engine was created from instead of
    this test's isolated in-memory one."""
    import agile_ci_demo.core.database as database_module

    db = next(app.dependency_overrides[get_db]())
    try:
        monkeypatch.setattr(database_module, "engine", db.get_bind())
    finally:
        db.close()


def test_encrypt_legacy_patient_pii_encrypts_existing_plaintext_rows(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A patient row written before column-level encryption existed (plain SQL
    INSERT, bypassing the ORM's EncryptedString/DeterministicEncryptedString)
    must get encrypted the next time the migration runs."""
    _use_test_engine_for_legacy_migration(client, monkeypatch)

    db = next(app.dependency_overrides[get_db]())
    try:
        db.execute(
            text("""
                INSERT INTO patients
                    (patient_id, full_name, date_of_birth, gender, phone_number,
                     email, ic_or_passport, address, created_at, updated_at)
                VALUES
                    (:patient_id, :full_name, :dob, :gender, :phone,
                     :email, :ic, :address, :now, :now)
                """),
            {
                "patient_id": "P00001",
                "full_name": "Legacy Patient",
                "dob": dt.date(1985, 3, 1).isoformat(),
                "gender": "male",
                "phone": "013-9998888",
                "email": "legacy@example.com",
                "ic": "850301-10-5555",
                "address": "Old Address",
                "now": dt.datetime.utcnow().isoformat(),
            },
        )
        db.commit()
    finally:
        db.close()

    encrypt_legacy_patient_pii()

    row = _raw_patient_row(client)
    assert row.phone_number != "013-9998888"
    assert row.ic_or_passport != "850301-10-5555"
    assert is_encrypted(row.phone_number)
    assert is_encrypted(row.ic_or_passport)

    # And it reads back correctly through the app, and is findable by exact IC.
    r = client.get("/api/patients/P00001")
    assert r.status_code == 200
    assert r.json()["ic_or_passport"] == "850301-10-5555"

    lookup = client.get("/api/patients/by-ic/850301-10-5555")
    assert lookup.status_code == 200
    assert lookup.json()["patient_id"] == "P00001"


def test_encrypt_legacy_patient_pii_is_idempotent(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-running the migration against already-encrypted data must not
    double-encrypt it - is_encrypted() is what makes this safe to run on
    every startup."""
    _use_test_engine_for_legacy_migration(client, monkeypatch)
    client.post("/api/patients", json=valid_patient_payload())

    before = _raw_patient_row(client)
    encrypt_legacy_patient_pii()
    after = _raw_patient_row(client)

    assert before.ic_or_passport == after.ic_or_passport
    assert before.phone_number == after.phone_number

    # Still decrypts correctly, not double-encrypted garbage.
    r = client.get("/api/patients/P00001")
    assert r.status_code == 200
    assert r.json()["ic_or_passport"] == "900520-10-1234"
