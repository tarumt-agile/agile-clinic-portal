from __future__ import annotations

from pydantic import BaseModel


class AdminDashboardStats(BaseModel):
    total_patients: int
    total_staff: int
    active_doctors: int
    appointments_today: int
