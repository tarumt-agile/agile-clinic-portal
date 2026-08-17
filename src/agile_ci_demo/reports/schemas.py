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


class MonthlyPatientRegistration(BaseModel):
    month: str
    count: int = Field(ge=0)


class MonthlyPatientRegistrationReport(BaseModel):
    year: int = Field(ge=1900, le=9998)
    total_registrations: int = Field(ge=0)
    monthly_registrations: list[MonthlyPatientRegistration]
