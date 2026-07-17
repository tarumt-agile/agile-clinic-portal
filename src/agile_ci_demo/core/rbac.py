from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """Staff roles supported by the portal."""

    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"


class Specialty(str, Enum):
    """Medical specialties used only for doctor staff accounts."""

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
