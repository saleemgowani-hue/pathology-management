"""
Seeds one standing demo lab so the login page can offer a working
"try it now" account without anyone needing a real license key.
Idempotent — safe to call on every startup.
"""
from datetime import date, timedelta

from utils.auth import hash_password
from db.models import Tenant, User

DEMO_LAB_CODE = "DEMO"
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo1234"


def seed_demo_account(session):
    tenant = session.query(Tenant).filter_by(lab_code=DEMO_LAB_CODE).first()
    if not tenant:
        tenant = Tenant(
            lab_code=DEMO_LAB_CODE,
            lab_name="PathoLab Demo Center",
            plan="yearly",
            status="active",
            activation_date=date.today(),
            expiry_date=date.today() + timedelta(days=3650),
            license_key="DEMO-SEEDED",
        )
        session.add(tenant)
        session.flush()
    else:
        # Keep the demo lab permanently unlocked even if the app has
        # been sitting untouched for years.
        if not tenant.expiry_date or (tenant.expiry_date - date.today()).days < 30:
            tenant.expiry_date = date.today() + timedelta(days=3650)
            tenant.status = "active"

    user = session.query(User).filter_by(tenant_id=tenant.id, username=DEMO_USERNAME).first()
    if not user:
        user = User(
            tenant_id=tenant.id,
            username=DEMO_USERNAME,
            full_name="Demo User",
            role="admin",
            mobile="",
            active=True,
            password_hash=hash_password(DEMO_PASSWORD),
        )
        session.add(user)

    session.commit()
