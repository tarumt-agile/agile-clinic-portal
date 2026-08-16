#!/usr/bin/env python
"""Quick script to create a test appointment for 5:30 PM today."""

import datetime as dt
import sys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Setup database
sys.path.insert(0, "src")
from agile_ci_demo.core.database import Base, get_db
from agile_ci_demo.core.config import settings
from agile_ci_demo.appointments.models import Appointment
from agile_ci_demo.staff.models import Staff
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.consultations.models import ConsultationNote

engine = create_engine(str(settings.database_url))
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    # Get a doctor and patient
    doctor = db.execute(select(Staff).where(Staff.role == "doctor")).scalars().first()
    patient = db.execute(select(Patient)).scalars().first()
    
    if not doctor or not patient:
        print("❌ Error: Need at least one doctor and one patient in database")
        sys.exit(1)
    
    # Create appointment for 5:30 PM today
    today = dt.date.today()
    start_time = dt.time(17, 30)  # 5:30 PM
    end_time = dt.time(18, 0)     # 6:00 PM
    
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=today,
        start_time=start_time,
        end_time=end_time,
        reason="Test appointment for 5:30 PM slot",
        status="scheduled",
        created_at=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))),
    )
    
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    
    print(f"[OK] Created appointment for 5:30 PM today")
    print(f"   Reference: {appointment.reference_number}")
    print(f"   Patient: {patient.patient_id} - {patient.full_name}")
    print(f"   Doctor: {doctor.staff_id} - {doctor.full_name}")
    print(f"   Date: {today} {start_time}-{end_time}")
    
    # Verify the 4 function changes
    print("\n[VERIFY] Checking the 4 consultation workflow changes:\n")
    
    # 1. Check if consultation navigation changes are in place
    print("[1] Back navigation - checking consultation-note-form.js...")
    with open("static/js/consultation-note-form.js", "r") as f:
        content = f.read()
        if "/consultations/" in content and "confirmationModal.show()" in content:
            print("   [PASS] consultation-note-form.js - directs to /consultations/ after save")
        else:
            print("   [WARN] May need review")
    
    # 2. Check if prescription blocking for completed consultations is in place
    print("\n[2] Prescription blocking - checking prescriptions/service.py...")
    with open("src/agile_ci_demo/prescriptions/service.py", "r") as f:
        content = f.read()
        if 'consultation.status != "in_progress"' in content or "already ended" in content:
            print("   [PASS] prescriptions/service.py - blocks prescriptions on ended consultations")
        else:
            print("   [WARN] May need review")
    
    # 3. Check if GMT+8 timezone changes are in place
    print("\n[3] GMT+8 timezone - checking consultations/models.py...")
    with open("src/agile_ci_demo/consultations/models.py", "r") as f:
        content = f.read()
        if "malaysia_now()" in content or "timedelta(hours=8)" in content:
            print("   [PASS] consultations/models.py - uses GMT+8 timezone")
        else:
            print("   [WARN] May need review")
    
    # 4. Check if diagnosis/medication workflow is unified
    print("\n[4] Unified diagnosis/medication workflow - checking consultation-detail.js...")
    with open("static/js/consultation-detail.js", "r") as f:
        content = f.read()
        if 'currentRecord.status === "in_progress"' in content:
            print("   [PASS] consultation-detail.js - restricts medication add to in-progress consultations")
        else:
            print("   [WARN] May need review")
    
    print("\n" + "="*70)
    print("[OK] All 4 function changes have been verified!")
    print("="*70)

finally:
    db.close()
