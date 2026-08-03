from __future__ import annotations

import re
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agile_ci_demo.app import app
from agile_ci_demo.core.database import Base, get_db
from agile_ci_demo.core.email import clear_outbox, get_outbox
from agile_ci_demo.pharmacy import models as _pharmacy_models  # noqa: F401
from agile_ci_demo.pharmacy.service import seed_default_medications


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)

    with testing_session_local() as db:
        seed_default_medications(db)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)

    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        clear_outbox()


def staff_payload(
    role: str,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "full_name": "Nora Ibrahim",
        "email": "nora@example.com",
        "role": role,
    }
    if role == "doctor":
        payload.update(
            {
                "license_number": "MMC-12345",
                "specialty": "General Medicine",
                "status": "active",
            }
        )
    payload.update(overrides)
    return payload


def create_staff_and_login(
    client: TestClient,
    role: str = "receptionist",
    **overrides: object,
) -> str:
    payload = staff_payload(role, **overrides)
    email = str(payload["email"])

    clear_outbox()
    create_response = client.post(
        "/api/staff",
        json=payload,
    )
    assert create_response.status_code == 201, create_response.json()

    welcome_email = next(message for message in reversed(get_outbox()) if message.to == email)
    match = re.search(
        r"temporary password is: (\S+)",
        welcome_email.body,
    )
    assert match is not None

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": match.group(1),
        },
    )
    assert login_response.status_code == 200, login_response.json()
    return str(create_response.json()["staff_id"])


def new_medication_payload(
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Amlodipine",
        "form": "Tablet",
        "standard_dosage": "5 mg",
        "unit": "tablets",
        "initial_stock": 25,
        "reorder_level": 5,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def create_medication(
    client: TestClient,
    **overrides: object,
) -> dict[str, object]:
    response = client.post(
        "/api/pharmacy/medications",
        json=new_medication_payload(**overrides),
    )
    assert response.status_code == 201, response.json()
    return response.json()


def test_seeded_catalogue_is_visible_to_receptionist(
    client: TestClient,
) -> None:
    create_staff_and_login(client)

    response = client.get("/api/pharmacy/medications")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 15
    assert any(item["prescription_value"] == "Paracetamol 500 mg Tablet" for item in body["items"])


def test_receptionist_can_create_medication_with_initial_stock(
    client: TestClient,
) -> None:
    staff_id = create_staff_and_login(client)
    medication = create_medication(client)

    assert medication["medication_id"].startswith("M")
    assert medication["prescription_value"] == "Amlodipine 5 mg Tablet"
    assert medication["stock_quantity"] == 25
    assert medication["unit"] == "tablets"
    assert medication["low_stock"] is False

    history_response = client.get(
        "/api/pharmacy/medications/" f"{medication['medication_id']}/transactions"
    )
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) == 1
    assert history[0]["transaction_type"] == "initial_stock"
    assert history[0]["quantity_change"] == 25
    assert history[0]["balance_after"] == 25
    assert history[0]["performed_by_staff_id"] == staff_id


def test_duplicate_medication_is_rejected(
    client: TestClient,
) -> None:
    create_staff_and_login(client)
    create_medication(client)

    response = client.post(
        "/api/pharmacy/medications",
        json=new_medication_payload(
            name="  amlodipine  ",
            form="Tablet",
        ),
    )

    assert response.status_code == 409


def test_medication_search_uses_catalogue_fields(
    client: TestClient,
) -> None:
    create_staff_and_login(client)

    response = client.get(
        "/api/pharmacy/medications",
        params={"q": "inhaler"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Salbutamol"


def test_receptionist_can_edit_and_deactivate_medication(
    client: TestClient,
) -> None:
    create_staff_and_login(client)
    medication = create_medication(client)

    response = client.patch(
        "/api/pharmacy/medications/" f"{medication['medication_id']}",
        json={
            "unit": "packs",
            "reorder_level": 30,
            "is_active": False,
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["unit"] == "packs"
    assert updated["reorder_level"] == 30
    assert updated["is_active"] is False
    assert updated["low_stock"] is True

    active_list = client.get(
        "/api/pharmacy/medications",
        params={"q": "Amlodipine"},
    )
    inactive_list = client.get(
        "/api/pharmacy/medications",
        params={
            "q": "Amlodipine",
            "include_inactive": True,
        },
    )
    assert active_list.json()["total"] == 0
    assert inactive_list.json()["total"] == 1

    create_staff_and_login(
        client,
        "doctor",
        full_name="Dr. David Lee",
        email="doctor@example.com",
        license_number="MMC-54321",
    )
    prescribing_search = client.get(
        "/api/prescriptions/medications",
        params={"q": "Amlodipine"},
    )
    assert prescribing_search.status_code == 200
    assert prescribing_search.json() == []


def test_stock_adjustments_update_balance_and_audit_history(
    client: TestClient,
) -> None:
    staff_id = create_staff_and_login(client)
    medication = create_medication(client)
    medication_id = str(medication["medication_id"])

    stock_in = client.post(
        f"/api/pharmacy/medications/{medication_id}/stock-adjustments",
        json={
            "quantity_change": 10,
            "reason": "Received supplier delivery.",
        },
    )
    stock_out = client.post(
        f"/api/pharmacy/medications/{medication_id}/stock-adjustments",
        json={
            "quantity_change": -4,
            "reason": "Removed damaged tablets.",
        },
    )

    assert stock_in.status_code == 200
    assert stock_in.json()["stock_quantity"] == 35
    assert stock_out.status_code == 200
    assert stock_out.json()["stock_quantity"] == 31

    history_response = client.get(f"/api/pharmacy/medications/{medication_id}/transactions")
    history = history_response.json()
    assert [item["quantity_change"] for item in history] == [
        -4,
        10,
        25,
    ]
    assert history[0]["balance_after"] == 31
    assert all(item["performed_by_staff_id"] == staff_id for item in history)


def test_stock_cannot_be_reduced_below_zero(
    client: TestClient,
) -> None:
    create_staff_and_login(client)
    medication = create_medication(client)

    response = client.post(
        "/api/pharmacy/medications/" f"{medication['medication_id']}/stock-adjustments",
        json={
            "quantity_change": -26,
            "reason": "Invalid excessive reduction.",
        },
    )

    assert response.status_code == 409

    detail_response = client.get("/api/pharmacy/medications/" f"{medication['medication_id']}")
    assert detail_response.json()["stock_quantity"] == 25


@pytest.mark.parametrize(
    "role",
    ["doctor", "nurse"],
)
def test_non_pharmacy_roles_cannot_manage_inventory(
    client: TestClient,
    role: str,
) -> None:
    overrides: dict[str, object] = {
        "full_name": "Dr. David Lee" if role == "doctor" else "Rina Lee",
        "email": f"{role}@example.com",
    }
    if role == "doctor":
        overrides["license_number"] = "MMC-54321"

    create_staff_and_login(
        client,
        role,
        **overrides,
    )

    response = client.get(
        "/api/pharmacy/medications",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


@pytest.mark.parametrize(
    "role",
    ["receptionist", "admin"],
)
def test_receptionist_and_admin_can_open_pharmacy_page(
    client: TestClient,
    role: str,
) -> None:
    create_staff_and_login(
        client,
        role,
        email=f"{role}@example.com",
    )

    response = client.get("/pharmacy")

    assert response.status_code == 200
    assert 'id="pharmacy-root"' in response.text
    assert 'id="add-medication-button"' in response.text
    assert 'id="stock-modal"' in response.text
    assert "/static/js/pharmacy-management.js" in response.text
    assert 'class="sidebar-link' in response.text and 'href="/pharmacy">Pharmacy</a>' in response.text


def test_pharmacy_form_uses_controlled_dropdowns(
    client: TestClient,
) -> None:
    create_staff_and_login(client)

    response = client.get("/pharmacy")

    assert response.status_code == 200
    assert 'id="medication-form-type"' in response.text
    assert 'id="medication-standard-dosage"' in response.text
    assert 'id="medication-unit"' in response.text
    assert response.text.count('class="form-select"') >= 3
    assert '<option value="Tablet">' in response.text
    assert '<option value="250 mg">' in response.text
    assert 'value="tablets"' in response.text


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("form", "Hand-typed form"),
        ("standard_dosage", "Hand-typed dosage"),
        ("unit", "Hand-typed unit"),
    ],
)
def test_medication_rejects_values_outside_dropdown_options(
    client: TestClient,
    field_name: str,
    invalid_value: str,
) -> None:
    create_staff_and_login(client)

    response = client.post(
        "/api/pharmacy/medications",
        json=new_medication_payload(
            **{field_name: invalid_value},
        ),
    )

    assert response.status_code == 422


def test_out_of_stock_quantity_has_bold_red_style() -> None:
    project_root = Path(__file__).resolve().parents[1]
    script = (project_root / "static" / "js" / "pharmacy-management.js").read_text(encoding="utf-8")
    stylesheet = (project_root / "static" / "css" / "pharmacy-management.css").read_text(
        encoding="utf-8"
    )

    assert 'class="pharmacy-stock-quantity"' in script
    assert 'return "pharmacy-stock-empty"' in script
    assert ".pharmacy-stock-empty .pharmacy-stock-quantity" in stylesheet
    assert "color: var(--bs-danger)" in stylesheet
    assert "font-weight: 800" in stylesheet


def test_pharmacy_page_requires_login(
    client: TestClient,
) -> None:
    response = client.get(
        "/pharmacy",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"
