from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """Staff roles supported by the portal. A staff account has exactly one role."""

    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"
    RECEPTIONIST = "receptionist"
    PHARMACIST = "pharmacist"


class Specialty(str, Enum):
    """Medical specialties a doctor account may be assigned. Only meaningful for
    staff with role=doctor - other roles do not have a specialty."""

    GENERAL_PRACTICE = "general_practice"
    PEDIATRICS = "pediatrics"
    CARDIOLOGY = "cardiology"
    DERMATOLOGY = "dermatology"
    ENT = "ent"
    ORTHOPEDICS = "orthopedics"
    GYNECOLOGY = "gynecology"
    PSYCHIATRY = "psychiatry"
    DENTISTRY = "dentistry"
    OPHTHALMOLOGY = "ophthalmology"
