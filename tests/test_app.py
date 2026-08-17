from fastapi.testclient import TestClient

from agile_ci_demo.app import app, reset_db

client = TestClient(app)


def setup_function() -> None:
    """Called by pytest before every test in this module."""
    reset_db()


def test_health():
    """
    Scenario: API health check
      Given the API is running
      When I GET /health
      Then I receive 200 and {"status": "ok"}
    """
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_and_get_item():
    """
    Scenario: Add a todo item
      Given the API is running
      When I POST /items with a new item
      Then I receive 201 and the item is persisted
    """
    item = {"id": 1, "title": "Read agile guide"}

    # Create
    r = client.post("/items", json=item)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1
    assert body["title"] == "Read agile guide"
    assert body["done"] is False

    # Read back
    r2 = client.get("/items/1")
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["id"] == 1
    assert body2["title"] == "Read agile guide"
    assert body2["done"] is False


def test_conflict_on_duplicate():
    """
    Scenario: Cannot create duplicate item IDs
      Given an item with ID 2 exists
      When I POST another item with ID 2
      Then I receive 409 Conflict
    """
    item = {"id": 2, "title": "Duplicate"}

    # First create succeeds
    r1 = client.post("/items", json=item)
    assert r1.status_code == 201

    # Second create fails
    r2 = client.post("/items", json=item)
    assert r2.status_code == 409


def test_mark_done():
    """
    Scenario: Mark an item as done
      Given an item with ID 3 exists
      When I PATCH /items/3/done
      Then the item is marked as done
    """
    item = {"id": 3, "title": "Finish demo"}
    client.post("/items", json=item)

    r = client.patch("/items/3/done")
    assert r.status_code == 200
    assert r.json()["done"] is True


def test_session_cookie_round_trips() -> None:
    """A FastAPI app with SessionMiddleware can set and read back a signed session value."""
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient as FastAPITestClient
    from starlette.middleware.sessions import SessionMiddleware

    probe_app = FastAPI()
    probe_app.add_middleware(SessionMiddleware, secret_key="test-secret")

    @probe_app.get("/write")
    def _write(request: Request) -> dict:
        request.session["probe"] = "hello"
        return {"ok": True}

    @probe_app.get("/read")
    def _read(request: Request) -> dict:
        return {"probe": request.session.get("probe")}

    probe_client = FastAPITestClient(probe_app)
    probe_client.get("/write")
    r = probe_client.get("/read")
    assert r.json() == {"probe": "hello"}
