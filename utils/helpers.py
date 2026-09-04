from datetime import date, datetime

from db.models import Patient, Sample, Bill, AuditLog, Setting


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
