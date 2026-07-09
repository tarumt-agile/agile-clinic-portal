from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """Staff roles supported by the portal. A staff account has exactly one role."""

    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"
    RECEPTIONIST = "receptionist"
    PHARMACIST = "pharmacist"
