from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class AttachmentOut(BaseModel):
    """A consultation attachment's metadata, returned after upload or in a list."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_by_name: str
    created_at: dt.datetime
