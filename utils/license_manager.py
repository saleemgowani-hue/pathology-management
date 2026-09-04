"""
No free trial in this platform: a new pathology lab can only be
registered by consuming a valid Monthly or Yearly license key, right at
sign-up time. See generate_license_keys.py (run by the vendor, never
shipped to labs) for how keys are created.
"""
import random
import re
import string
from datetime import date, datetime, timedelta

from db.models import Tenant, LicenseKey, User

PLAN_DAYS = {"monthly": 30, "yearly": 365}


def _slugify(lab_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "", lab_name).upper()[:8]
    return slug or "LAB"


def generate_lab_code(session, lab_name: str) -> str:
    """A short, human-typeable code the lab's staff use at login,
    alongside their username/password, to identify which lab they
    belong to (usernames are unique per-lab, not globally)."""
    base = _slugify(lab_name)
    for _ in range(50):
        candidate = f"{base}{random.randint(100, 999)}"
        if not session.query(Tenant).filter_by(lab_code=candidate).first():
            return candidate
    # extremely unlikely fallback
    return f"{base}{random.randint(1000, 9999)}"


def register_tenant(session, lab_name: str, key_code: str):
    """Validates and consumes a license key, creates the Tenant row.
    Returns (tenant_or_None, error_message_or_None)."""
    key_norm = key_code.strip().upper()
    pool_key = session.query(LicenseKey).filter_by(key_code=key_norm).first()
    if not pool_key:
        return None, "This license key is not valid. Please check and re-enter it."
    if pool_key.is_used:
        return None, "This license key has already been used to register a lab."

    plan = pool_key.plan if pool_key.plan in PLAN_DAYS else "yearly"
    today = date.today()
    lab_code = generate_lab_code(session, lab_name)

    tenant = Tenant(
        lab_code=lab_code, lab_name=lab_name.strip(), plan=plan, status="active",
        activation_date=today, expiry_date=today + timedelta(days=PLAN_DAYS[plan]),
        license_key=key_norm,
    )
    session.add(tenant)
    session.flush()

    pool_key.is_used = True
    pool_key.used_by_tenant_id = tenant.id
    pool_key.activated_date = datetime.utcnow()

    session.commit()
    return tenant, None


def tenant_status(tenant: Tenant):
    """Returns a dict describing whether this tenant's subscription is
    still valid. No trial exists anywhere in this platform — every
    tenant's access is tied entirely to the key they registered with."""
    today = date.today()
    if not tenant.expiry_date:
        return {"locked": True, "status": "unlicensed", "remaining_days": 0}
    remaining = (tenant.expiry_date - today).days
    if remaining < 0:
        if tenant.status != "expired":
            tenant.status = "expired"
        return {"locked": True, "status": "expired", "remaining_days": 0}
    if tenant.status == "expired":
        tenant.status = "active"
    return {"locked": False, "status": "active", "remaining_days": remaining}


def renew_tenant(session, tenant: Tenant, key_code: str):
    """An existing lab's admin renews with a fresh key (Monthly or
    Yearly) once their subscription is close to expiry or has lapsed."""
    key_norm = key_code.strip().upper()
    pool_key = session.query(LicenseKey).filter_by(key_code=key_norm).first()
    if not pool_key:
        return False, "This license key is not valid. Please check and re-enter it."
    if pool_key.is_used:
        return False, "This license key has already been used."

    plan = pool_key.plan if pool_key.plan in PLAN_DAYS else "yearly"
    today = date.today()
    # Renewing before expiry extends from the current expiry date rather
    # than from today, so labs don't lose paid-for days by renewing early.
    base_date = tenant.expiry_date if tenant.expiry_date and tenant.expiry_date > today else today
    tenant.plan = plan
    tenant.status = "active"
    tenant.expiry_date = base_date + timedelta(days=PLAN_DAYS[plan])
    tenant.license_key = key_norm

    pool_key.is_used = True
    pool_key.used_by_tenant_id = tenant.id
    pool_key.activated_date = datetime.utcnow()

    session.commit()
    return True, f"Renewed successfully — {plan.capitalize()} plan, valid until {tenant.expiry_date}."
