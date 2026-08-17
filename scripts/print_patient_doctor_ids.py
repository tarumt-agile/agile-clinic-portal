from sqlalchemy import select
from agile_ci_demo.core.database import SessionLocal, init_db
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.staff.models import Staff

init_db()
with SessionLocal() as db:
    patients = db.execute(select(Patient).order_by(Patient.id).limit(10)).scalars().all()
    doctors = db.execute(select(Staff).where(Staff.role == 'doctor').order_by(Staff.id).limit(10)).scalars().all()
    print('PATIENTS')
    for p in patients:
        print(p.patient_id, p.full_name)
    print('DOCTORS')
    for d in doctors:
        print(d.staff_id, d.full_name, d.role)
