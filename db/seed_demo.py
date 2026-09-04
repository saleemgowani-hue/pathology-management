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
import random
from datetime import date, datetime, timedelta

from utils.auth import hash_password
from utils.helpers import add_demo_patients, next_receipt_number, next_sample_number, get_setting, set_setting
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

_DOCTOR_DEFS = [
    ("Dr. Anita Sharma", "MBBS, MD", "General Physician"),
    ("Dr. Rajesh Verma", "MBBS, MS", "Orthopedics"),
    ("Dr. Priya Nair", "MBBS, DGO", "Gynecology"),
    ("Dr. Sanjay Gupta", "MBBS, MD", "Cardiology"),
    ("Dr. Kavita Iyer", "MBBS, DCH", "Pediatrics"),
]
_PATHOLOGIST_DEFS = [
    ("Dr. Meera Desai", "MD Pathology", "REG-2019-4521", "Histopathology"),
    ("Dr. Arvind Rao", "MD Pathology", "REG-2015-3390", "Clinical Pathology"),
]
# code, name, category, sample_type, normal_range, unit, price, result_value, result_flag
_TEST_DEFS = [
    ("CBC01", "Complete Blood Count", "Hematology", "Blood (EDTA)", "4.5-11.0 x10^9/L", "x10^9/L", 350, "7.8", "Normal"),
    ("LFT01", "Liver Function Test", "Liver Function Test", "Serum", "7-56 U/L", "U/L", 700, "32", "Normal"),
    ("KFT01", "Kidney Function Test", "Kidney Function Test", "Serum", "0.6-1.3 mg/dL", "mg/dL", 650, "1.0", "Normal"),
    ("LIP01", "Lipid Profile", "Lipid Profile", "Serum", "<200 mg/dL", "mg/dL", 600, "185", "Normal"),
    ("THY01", "Thyroid Profile (T3 T4 TSH)", "Thyroid Profile", "Serum", "0.4-4.0 mIU/L", "mIU/L", 800, "2.1", "Normal"),
    ("GLU01", "Fasting Blood Sugar", "Diabetes Tests", "Plasma", "70-100 mg/dL", "mg/dL", 150, "92", "Normal"),
    ("HBA1C", "HbA1c", "Diabetes Tests", "Blood (EDTA)", "<5.7 %", "%", 500, "5.4", "Normal"),
    ("URN01", "Urine Routine & Microscopy", "Clinical Pathology", "Urine", "Normal", "-", 200, "Normal", "Normal"),
    ("ESR01", "ESR", "Hematology", "Blood (EDTA)", "0-20 mm/hr", "mm/hr", 150, "14", "Normal"),
    ("VITD", "Vitamin D (25-OH)", "Biochemistry", "Serum", "30-100 ng/mL", "ng/mL", 1200, "28", "Low"),
    ("VITB12", "Vitamin B12", "Biochemistry", "Serum", "200-900 pg/mL", "pg/mL", 900, "650", "Normal"),
    ("CRP01", "CRP (Quantitative)", "Serology", "Serum", "<5 mg/L", "mg/L", 450, "3.2", "Normal"),
]
_PACKAGE_DEFS = [
    ("Full Body Checkup Basic", ["CBC01", "LFT01", "KFT01", "LIP01", "GLU01"], 2200),
    ("Diabetes Screening Package", ["GLU01", "HBA1C", "LIP01"], 1100),
]
_STAFF_DEFS = [
    ("Sunil Verma", "Lab Technician", 22000),
    ("Priya Reddy", "Receptionist", 18000),
    ("Amit Joshi", "Phlebotomist", 20000),
    ("Deepa Nair", "Accountant", 25000),
]
_INVENTORY_DEFS = [
    ("EDTA Vacutainer Tubes", "Consumables", "pcs", 250, 100),
    ("Plain Vacutainer Tubes", "Consumables", "pcs", 180, 100),
    ("Syringes 5ml", "Consumables", "pcs", 15, 50),
    ("Reagent Kit - LFT", "Reagents", "kits", 3, 5),
    ("Reagent Kit - Lipid Profile", "Reagents", "kits", 8, 5),
    ("Gloves (Box of 100)", "PPE", "boxes", 20, 10),
    ("Alcohol Swabs", "Consumables", "packs", 40, 20),
    ("Centrifuge Tubes", "Consumables", "pcs", 12, 30),
]
_EXPENSE_DEFS = [
    ("Electricity", "Monthly electricity bill", 4500, "Bank Transfer"),
    ("Rent", "Lab premises rent", 25000, "Bank Transfer"),
    ("Consumables", "Reagent restock", 8000, "Cash"),
    ("Maintenance", "Centrifuge servicing", 1500, "Cash"),
    ("Equipment", "New microscope lens", 3200, "UPI"),
]


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


def _ensure_reference_data(session, tenant_id):
    """Doctors, pathologists, tests and packages have tenant-unique
    codes, so unlike patients they can't just be re-added every time
    "Add Demo Data" is clicked -- that would crash on the second
    click. Create them only if this tenant doesn't have any yet;
    otherwise just return what's already there."""
    doctors = session.query(Doctor).filter_by(tenant_id=tenant_id).all()
    if not doctors:
        for name, qual, spec in _DOCTOR_DEFS:
            d = Doctor(tenant_id=tenant_id, name=name, qualification=qual, specialization=spec,
                       mobile=f"9{random.randint(100000000, 999999999)}",
                       commission_percent=random.choice([0, 5, 10]), active=True)
            session.add(d)
            doctors.append(d)
        session.flush()

    pathologists = session.query(Pathologist).filter_by(tenant_id=tenant_id).all()
    if not pathologists:
        for name, qual, reg, spec in _PATHOLOGIST_DEFS:
            p = Pathologist(tenant_id=tenant_id, name=name, qualification=qual,
                             registration_number=reg, specialization=spec, active=True)
            session.add(p)
            pathologists.append(p)
        session.flush()

    tests = session.query(TestItem).filter_by(tenant_id=tenant_id).all()
    if not tests:
        for code, name, cat, sample_type, nrange, unit, price, _val, _flag in _TEST_DEFS:
            t = TestItem(tenant_id=tenant_id, test_code=code, name=name, category=cat,
                         sample_type=sample_type, normal_range=nrange, unit=unit, price=price,
                         department=cat, method="Automated", turnaround_time="Same day", active=True)
            session.add(t)
            tests.append(t)
        session.flush()

        tests_by_code = {t.test_code: t for t in tests}
        for name, codes, price in _PACKAGE_DEFS:
            prof = TestProfile(tenant_id=tenant_id, name=name, price=price, active=True)
            session.add(prof)
            session.flush()
            for code in codes:
                session.add(TestProfileItem(profile_id=prof.id, test_id=tests_by_code[code].id))
        session.flush()

    return doctors, pathologists, tests


def _seed_samples_and_results(session, tenant_id, patients, tests, pathologists, demo_user_id):
    """For 12 of the given patients: collect a sample with 1-3 random
    tests. 8 of those get results entered and a report (5 locked/
    verified, 3 still in draft); the other 4 stay pending in the
    Result Entry queue -- so every stage of the clinical workflow has
    something in it."""
    result_by_code = {t[0]: (t[7], t[8]) for t in _TEST_DEFS}
    sample_patients = patients[:12]
    for i, patient in enumerate(sample_patients):
        sample_number = next_sample_number(session, tenant_id)
        sample = Sample(tenant_id=tenant_id, sample_number=sample_number, patient_id=patient.id,
                         sample_type="Blood (EDTA)", status="Collected", collected_by="Demo User",
                         collection_datetime=datetime.utcnow())
        session.add(sample)
        session.flush()

        chosen_tests = random.sample(tests, k=min(random.randint(1, 3), len(tests)))
        orders = []
        for t in chosen_tests:
            order = TestOrder(tenant_id=tenant_id, sample_id=sample.id, test_id=t.id, status="Pending")
            session.add(order)
            orders.append((order, t))
        session.flush()

        if i < 8:
            for order, t in orders:
                val, flag = result_by_code.get(t.test_code, ("Normal", "Normal"))
                session.add(TestResult(
                    tenant_id=tenant_id, test_order_id=order.id, parameter=t.name,
                    result=val, unit=t.unit, reference_range=t.normal_range,
                    flag=flag, technician_id=demo_user_id, result_datetime=datetime.utcnow(),
                ))
                order.status = "Completed"
            sample.status = "Completed"

            report = Report(tenant_id=tenant_id, sample_id=sample.id, status="Draft")
            if i < 5:
                report.status = "Locked"
                report.pathologist_id = random.choice(pathologists).id if pathologists else None
                report.verified_by = demo_user_id
                report.verified_at = datetime.utcnow()
                report.remarks = "Reviewed — within expected limits."
            session.add(report)
        else:
            session.add(Report(tenant_id=tenant_id, sample_id=sample.id, status="Draft"))
    session.flush()


def _seed_bills(session, tenant_id, patients, tests, demo_user_id):
    """Bills for 10 of the given patients -- some fully paid, some
    partially, so Billing, Reports, and Pending Payments all have
    real numbers."""
    for i, patient in enumerate(patients[:10]):
        chosen = random.sample(tests, k=min(random.randint(1, 2), len(tests)))
        gross = sum(t.price for t in chosen)
        discount = round(gross * 0.05, 0) if i % 3 == 0 else 0
        net = gross - discount
        paid = net if i % 3 != 2 else round(net * 0.5, 0)  # every 3rd bill is a partial payment
        receipt_number = next_receipt_number(session, tenant_id)
        bill = Bill(tenant_id=tenant_id, receipt_number=receipt_number, patient_id=patient.id,
                    gross_amount=gross, discount=discount, net_amount=net, paid_amount=paid,
                    due_amount=net - paid, payment_mode="Cash", status="Active",
                    created_by=demo_user_id, created_at=datetime.utcnow())
        session.add(bill)
        session.flush()
        for t in chosen:
            session.add(BillItem(tenant_id=tenant_id, bill_id=bill.id, description=t.name, price=t.price))
        if paid > 0:
            session.add(Payment(tenant_id=tenant_id, bill_id=bill.id, amount=paid, mode="Cash", date=datetime.utcnow()))
    session.flush()


def _seed_staff_inventory_expenses(session, tenant_id, demo_user_id):
    staff_list = session.query(Staff).filter_by(tenant_id=tenant_id).all()
    if not staff_list:
        for i, (name, designation, salary) in enumerate(_STAFF_DEFS, start=1):
            s = Staff(tenant_id=tenant_id, staff_code=f"STF{i:03d}", name=name, designation=designation,
                      mobile=f"9{random.randint(100000000, 999999999)}", joining_date=date.today(),
                      salary=salary, status="Active")
            session.add(s)
            staff_list.append(s)
        session.flush()
        for i, s in enumerate(staff_list):
            session.add(Attendance(tenant_id=tenant_id, staff_id=s.id, date=date.today(),
                                    status="Present" if i < 3 else "Leave"))

    if not session.query(InventoryItem).filter_by(tenant_id=tenant_id).first():
        for name, category, unit, stock, min_stock in _INVENTORY_DEFS:
            session.add(InventoryItem(tenant_id=tenant_id, name=name, category=category, unit=unit,
                                       current_stock=stock, min_stock=min_stock))

    for category, desc, amount, mode in _EXPENSE_DEFS:
        session.add(Expense(tenant_id=tenant_id, date=date.today(), category=category, description=desc,
                             amount=amount, payment_mode=mode, added_by=demo_user_id))
    session.flush()


def seed_full_demo_data(session, tenant_id, patient_count=20):
    """The real "Add Demo Data" seeder: not just patients, but doctors,
    pathologists, tests, packages, samples carried through result entry
    and report verification, bills with payments, staff with
    attendance, inventory, and expenses -- so every module has
    something in it, not just the Patients list. Safe to call
    repeatedly: reference data (doctors/tests/packages/staff/inventory)
    is only created once per tenant, while patients/samples/bills/
    expenses are added fresh on every call."""
    demo_user = session.query(User).filter_by(tenant_id=tenant_id, username=DEMO_USERNAME).first()
    demo_user_id = demo_user.id if demo_user else None

    doctors, pathologists, tests = _ensure_reference_data(session, tenant_id)
    patients = add_demo_patients(session, tenant_id, count=patient_count, doctor_ids=[d.id for d in doctors])
    if tests:
        _seed_samples_and_results(session, tenant_id, patients, tests, pathologists, demo_user_id)
        _seed_bills(session, tenant_id, patients, tests, demo_user_id)
    _seed_staff_inventory_expenses(session, tenant_id, demo_user_id)
    session.commit()
    return patients


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
    # Patients reference Doctor via referring_doctor_id, so patients
    # must go before doctors, not after.
    session.query(Patient).filter_by(tenant_id=tenant_id).delete()
    session.query(Doctor).filter_by(tenant_id=tenant_id).delete()
    session.query(Pathologist).filter_by(tenant_id=tenant_id).delete()
    session.query(Setting).filter_by(tenant_id=tenant_id).delete()
    # Anyone added beyond the seeded login (shouldn't happen now that
    # adding staff is disabled for this tenant, but clean up safely
    # in case older data exists from before that restriction).
    session.query(User).filter(User.tenant_id == tenant_id, User.username != DEMO_USERNAME) \
        .delete(synchronize_session=False)
    session.commit()

    seed_full_demo_data(session, tenant_id, patient_count=20)
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
