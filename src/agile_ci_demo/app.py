from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agile_ci_demo.core.config import settings
from agile_ci_demo.core.database import init_db
from agile_ci_demo.patients.router import api_router as patients_api_router
from agile_ci_demo.patients.router import pages_router as patients_pages_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="Agile Clinic Portal", version="0.1.0", lifespan=lifespan)

if settings.static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

app.include_router(patients_api_router)
app.include_router(patients_pages_router)


class Item(BaseModel):
    id: int
    title: str
    done: bool = False


# naive in-memory "database" – fine for a teaching/demo app
_db: Dict[int, Item] = {}


@app.get("/health")
def health() -> dict:
    """Simple health check endpoint used by tests and monitoring."""
    return {"status": "ok"}


@app.post("/items", status_code=201)
def create_item(item: Item) -> Item:
    """Create a new todo item.

    Returns 409 if an item with the same ID already exists.
    """
    if item.id in _db:
        raise HTTPException(status_code=409, detail="Item with that ID already exists")

    _db[item.id] = item
    return item


@app.get("/items/{item_id}")
def get_item(item_id: int) -> Item:
    """Fetch a single item by ID."""
    if item_id not in _db:
        raise HTTPException(status_code=404, detail="Not found")
    return _db[item_id]


@app.patch("/items/{item_id}/done")
def mark_done(item_id: int) -> Item:
    """Mark an item as done."""
    if item_id not in _db:
        raise HTTPException(status_code=404, detail="Not found")

    item = _db[item_id]
    item.done = True
    _db[item_id] = item
    return item


# Optional: helper for tests to reset state (not exposed as an endpoint)
def reset_db() -> None:
    _db.clear()
