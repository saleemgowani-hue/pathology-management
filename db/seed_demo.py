"""
Seeds one standing demo lab so the login page can offer a working
"try it now" account without anyone needing a real license key.
Idempotent — safe to call on every startup.

Because the demo login (and its password) are shown right on the
login page, anyone can sign in as its admin. Two things protect it
from being turned into a free real account or left full of junk:
- Adding new staff accounts is disabled for this tenant specifically
  (see pages/14_User_Management.py) so nobody can plant a persistent
  login there.
- reset_demo_data()/maybe_auto_reset_demo() wipe every record the
  demo tenant owns and reseed the baseline patients at most once an
  hour, so anything a visitor typed in doesn't stick around.
"""
from datetime import date, datetime, timedelta

from utils.auth import hash_password
from utils.helpers import add_demo_patients, get_setting, set_setting
from db.models import (
    Tenant, User, Patient, Doctor, Pathologist, TestItem, TestProfile, TestProfileItem,
    Sample, TestOrder, TestResult, Report, Bill, BillItem, Payment, Staff, Attendance,
    InventoryItem, InventoryTransaction, Expense, Setting, AuditLog,
)

DEMO_LAB_CODE = "DEMO"
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo1234"
DEMO_RESET_INTERVAL_MINUTES = 60
_LAST_RESET_KEY = "_demo_last_reset"


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


def reset_demo_data(session, tenant_id):
    """Wipes every record the given tenant owns (patients, samples,
    bills, doctors, tests, staff, inventory, expenses, ...) but leaves
    the tenant and its seeded login user alone, then reseeds the 20
    baseline demo patients. Used both by the manual "Remove Demo Data"
    button and by the automatic hourly reset."""
    session.query(AuditLog).filter_by(tenant_id=tenant_id).delete()
    session.query(Payment).filter_by(tenant_id=tenant_id).delete()
    session.query(BillItem).filter_by(tenant_id=tenant_id).delete()
    session.query(Bill).filter_by(tenant_id=tenant_id).delete()
    session.query(TestResult).filter_by(tenant_id=tenant_id).delete()
    session.query(TestOrder).filter_by(tenant_id=tenant_id).delete()
    session.query(Report).filter_by(tenant_id=tenant_id).delete()
    session.query(Sample).filter_by(tenant_id=tenant_id).delete()
    session.query(Attendance).filter_by(tenant_id=tenant_id).delete()
    session.query(Staff).filter_by(tenant_id=tenant_id).delete()
    session.query(InventoryTransaction).filter_by(tenant_id=tenant_id).delete()
    session.query(InventoryItem).filter_by(tenant_id=tenant_id).delete()
    session.query(Expense).filter_by(tenant_id=tenant_id).delete()

    profile_ids = [p.id for p in session.query(TestProfile.id).filter_by(tenant_id=tenant_id)]
    if profile_ids:
        session.query(TestProfileItem).filter(TestProfileItem.profile_id.in_(profile_ids)) \
            .delete(synchronize_session=False)
    session.query(TestProfile).filter_by(tenant_id=tenant_id).delete()
    session.query(TestItem).filter_by(tenant_id=tenant_id).delete()
    session.query(Doctor).filter_by(tenant_id=tenant_id).delete()
    session.query(Pathologist).filter_by(tenant_id=tenant_id).delete()
    session.query(Patient).filter_by(tenant_id=tenant_id).delete()
    session.query(Setting).filter_by(tenant_id=tenant_id).delete()
    # Anyone added beyond the seeded login (shouldn't happen now that
    # adding staff is disabled for this tenant, but clean up safely
    # in case older data exists from before that restriction).
    session.query(User).filter(User.tenant_id == tenant_id, User.username != DEMO_USERNAME) \
        .delete(synchronize_session=False)
    session.commit()

    add_demo_patients(session, tenant_id, count=20)
    # Re-stamp *after* reseeding (which also wiped Settings) so both a
    # manual reset and an automatic one restart the 60-minute timer.
    set_setting(session, tenant_id, _LAST_RESET_KEY, datetime.utcnow().isoformat())


def maybe_auto_reset_demo(session):
    """Call on every page load for the demo tenant. If it's been more
    than DEMO_RESET_INTERVAL_MINUTES since the last reset, wipes and
    reseeds it -- so anything a visitor entered gets cleared out
    automatically, at most an hour later."""
    tenant = session.query(Tenant).filter_by(lab_code=DEMO_LAB_CODE).first()
    if not tenant:
        return
    last_reset_str = get_setting(session, tenant.id, _LAST_RESET_KEY)
    needs_reset = True
    if last_reset_str:
        try:
            needs_reset = (datetime.utcnow() - datetime.fromisoformat(last_reset_str)) > timedelta(minutes=DEMO_RESET_INTERVAL_MINUTES)
        except ValueError:
            needs_reset = True
    if needs_reset:
        reset_demo_data(session, tenant.id)
