from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class DailyAppointmentTotal(BaseModel):
    date: dt.date
    total: int = Field(ge=0)


class AppointmentActivityReport(BaseModel):
    from_date: dt.date
    to_date: dt.date
    selected_range_label: str
    total_appointments: int = Field(ge=0)
    daily_totals: list[DailyAppointmentTotal]
