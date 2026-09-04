import random
from datetime import date, datetime

from sqlalchemy import func

from db.models import Patient, Sample, Bill, AuditLog, Setting

DEMO_FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
    "Ananya", "Diya", "Saanvi", "Aadhya", "Kiara", "Myra", "Anika", "Navya", "Riya", "Priya",
]
DEMO_LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Singh", "Kumar", "Patel", "Reddy", "Nair", "Iyer", "Joshi",
    "Mehta", "Shah", "Chopra", "Malhotra", "Rao", "Pillai", "Desai", "Kapoor", "Bhat", "Agarwal",
]
DEMO_AREAS = ["MG Road", "Park Street", "Sector 21", "Civil Lines", "Anna Nagar", "Banjara Hills", "Koramangala"]


def add_demo_patients(session, tenant_id, count=20, doctor_ids=None):
    """Seeds `count` fake patients for the given tenant, for trying out
    the app without typing in real data by hand. Idempotent-safe to
    call repeatedly — each call just adds `count` more. Pass
    `doctor_ids` to randomly assign each new patient a referring
    doctor (so the Doctors page and Doctor-wise Report have real
    numbers to show)."""
    created = []
    for _ in range(count):
        name = f"{random.choice(DEMO_FIRST_NAMES)} {random.choice(DEMO_LAST_NAMES)}"
        code = next_patient_code(session, tenant_id)
        p = Patient(
            tenant_id=tenant_id,
            patient_code=code,
            name=name,
            age=random.randint(1, 85),
            gender=random.choice(["Male", "Female"]),
            mobile=f"9{random.randint(100000000, 999999999)}",
            address=f"{random.choice(DEMO_AREAS)}",
            email="",
            referring_doctor_id=random.choice(doctor_ids) if doctor_ids else None,
            patient_type=random.choice(["New", "Existing"]),
            registration_date=date.today(),
            notes="Demo patient (seeded for testing)",
        )
        session.add(p)
        session.flush()  # so the next next_patient_code() call sees this one
        created.append(p)
    session.commit()
    return created


def doctor_stats(session, tenant_id):
    """Returns {doctor_id: {"patients": int, "revenue": float}} for
    every doctor in one pair of grouped queries, instead of two
    queries per doctor (used by the Doctors page and the Doctor-wise
    Report, both of which used to query per-row in a loop)."""
    counts = dict(
        session.query(Patient.referring_doctor_id, func.count(Patient.id))
        .filter(Patient.tenant_id == tenant_id, Patient.referring_doctor_id.isnot(None))
        .group_by(Patient.referring_doctor_id).all()
    )
    revenues = dict(
        session.query(Patient.referring_doctor_id, func.sum(Bill.net_amount))
        .join(Bill, Bill.patient_id == Patient.id)
        .filter(Patient.tenant_id == tenant_id, Bill.status == "Active", Patient.referring_doctor_id.isnot(None))
        .group_by(Patient.referring_doctor_id).all()
    )
    doctor_ids = set(counts) | set(revenues)
    return {did: {"patients": counts.get(did, 0), "revenue": revenues.get(did, 0) or 0} for did in doctor_ids}


def next_patient_code(session, tenant_id):
    today = date.today()
    prefix = f"P{today.strftime('%y%m%d')}"
    count = session.query(Patient).filter(
        Patient.tenant_id == tenant_id, Patient.patient_code.like(f"{prefix}%")
    ).count() + 1
    return f"{prefix}{count:03d}"


def next_sample_number(session, tenant_id):
    today = date.today()
    prefix = f"S{today.strftime('%y%m%d')}"
    count = session.query(Sample).filter(
        Sample.tenant_id == tenant_id, Sample.sample_number.like(f"{prefix}%")
    ).count() + 1
    return f"{prefix}{count:03d}"


def next_receipt_number(session, tenant_id):
    today = date.today()
    prefix = f"R{today.strftime('%y%m%d')}"
    count = session.query(Bill).filter(
        Bill.tenant_id == tenant_id, Bill.receipt_number.like(f"{prefix}%")
    ).count() + 1
    return f"{prefix}{count:03d}"


def log_action(session, tenant_id, user_id, action, record_id=None, details=None):
    entry = AuditLog(
        tenant_id=tenant_id, user_id=user_id, action=action,
        record_id=str(record_id) if record_id is not None else None, details=details,
    )
    session.add(entry)
    session.commit()


def get_setting(session, tenant_id, key, default=""):
    row = session.query(Setting).filter_by(tenant_id=tenant_id, key=key).first()
    return row.value if row else default


def set_setting(session, tenant_id, key, value):
    row = session.query(Setting).filter_by(tenant_id=tenant_id, key=key).first()
    if row:
        row.value = value
    else:
        session.add(Setting(tenant_id=tenant_id, key=key, value=value))
    session.commit()


def get_settings_dict(session, tenant_id):
    rows = session.query(Setting).filter_by(tenant_id=tenant_id).all()
    return {r.key: r.value for r in rows}
