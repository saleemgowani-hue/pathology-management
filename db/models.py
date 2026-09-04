"""
Data model for the multi-tenant version of PathoLab Pro.

Multi-tenancy strategy: one shared Postgres database, one set of tables,
every business table carries a `tenant_id` column (row-level isolation).
This is the simplest reliable approach for a small number of tenants on
Neon's free/scale tiers, and every query in this app is written to filter
by tenant_id — see utils/tenant.py for the helper that enforces this.

`Tenant` and `LicenseKey` are the only tables that are NOT tenant-scoped:
- `Tenant` IS the tenant (one row per registered pathology lab).
- `LicenseKey` is the vendor's global pool of unissued keys — a brand
  new tenant consumes one of these at registration time.
"""
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, Text,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ---------------------------------------------------------------------------
# Tenancy & licensing (NOT tenant-scoped — these tables define tenants)
# ---------------------------------------------------------------------------

class Tenant(Base):
    """One row per registered pathology lab (a 'tenant' of the platform)."""
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True)
    lab_code = Column(String(20), unique=True, nullable=False)  # short code used at login
    lab_name = Column(String(150), nullable=False)
    plan = Column(String(20))  # monthly, yearly
    status = Column(String(20), default="active")  # active, expired
    activation_date = Column(Date)
    expiry_date = Column(Date)
    license_key = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)


class LicenseKey(Base):
    """Vendor-controlled pool of unissued keys (see utils/generate_license_keys.py).
    Never exposed inside the app itself — only the vendor holds these,
    in license_keys.xlsx, and hands one out per new lab that registers."""
    __tablename__ = "license_keys"
    id = Column(Integer, primary_key=True)
    key_code = Column(String(29), unique=True, nullable=False)
    plan = Column(String(20), default="yearly")  # monthly (30 days) or yearly (365 days)
    is_used = Column(Boolean, default=False)
    used_by_tenant_id = Column(Integer, ForeignKey("tenants.id"))
    activated_date = Column(DateTime)


# ---------------------------------------------------------------------------
# Tenant-scoped tables — every one of these has a tenant_id
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    username = Column(String(50), nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(120), nullable=False)
    role = Column(String(30), nullable=False)  # admin, receptionist, technician, doctor, accountant
    mobile = Column(String(20))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("tenant_id", "username", name="uq_tenant_username"),)


class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String(120), nullable=False)
    qualification = Column(String(120))
    specialization = Column(String(120))
    mobile = Column(String(20))
    address = Column(String(255))
    email = Column(String(120))
    commission_percent = Column(Float, default=0)
    active = Column(Boolean, default=True)


class Pathologist(Base):
    __tablename__ = "pathologists"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String(120), nullable=False)
    qualification = Column(String(120))
    registration_number = Column(String(60))
    specialization = Column(String(120))
    active = Column(Boolean, default=True)


class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    patient_code = Column(String(20), nullable=False)
    name = Column(String(120), nullable=False)
    age = Column(Integer)
    gender = Column(String(10))
    mobile = Column(String(20))
    address = Column(String(255))
    email = Column(String(120))
    referring_doctor_id = Column(Integer, ForeignKey("doctors.id"))
    patient_type = Column(String(20), default="New")
    registration_date = Column(Date, default=date.today)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("tenant_id", "patient_code", name="uq_tenant_patient_code"),)

    referring_doctor = relationship("Doctor")


class TestItem(Base):
    __tablename__ = "tests"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    test_code = Column(String(30), nullable=False)
    name = Column(String(150), nullable=False)
    category = Column(String(80))
    sample_type = Column(String(60))
    normal_range = Column(String(120))
    unit = Column(String(30))
    price = Column(Float, default=0)
    department = Column(String(80))
    method = Column(String(120))
    turnaround_time = Column(String(60))
    active = Column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "test_code", name="uq_tenant_test_code"),)


class TestProfile(Base):
    """A package/panel of tests sold together at a fixed price (e.g. 'Full Body Checkup')."""
    __tablename__ = "test_profiles"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String(150), nullable=False)
    price = Column(Float, default=0)
    active = Column(Boolean, default=True)


class TestProfileItem(Base):
    __tablename__ = "test_profile_items"
    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("test_profiles.id"), nullable=False)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False)


class Sample(Base):
    __tablename__ = "samples"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    sample_number = Column(String(30), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    collection_datetime = Column(DateTime, default=datetime.utcnow)
    sample_type = Column(String(60))
    status = Column(String(30), default="Collected")
    collected_by = Column(String(120))
    __table_args__ = (UniqueConstraint("tenant_id", "sample_number", name="uq_tenant_sample_number"),)

    patient = relationship("Patient")
    orders = relationship("TestOrder", backref="sample", cascade="all, delete-orphan")
    report = relationship("Report", backref="sample", uselist=False, cascade="all, delete-orphan")


class TestOrder(Base):
    __tablename__ = "test_orders"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    sample_id = Column(Integer, ForeignKey("samples.id"), nullable=False)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False)
    status = Column(String(30), default="Pending")

    test = relationship("TestItem")
    results = relationship("TestResult", backref="order", cascade="all, delete-orphan")


class TestResult(Base):
    __tablename__ = "test_results"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    test_order_id = Column(Integer, ForeignKey("test_orders.id"), nullable=False)
    parameter = Column(String(120), nullable=False)
    result = Column(String(120))
    unit = Column(String(30))
    reference_range = Column(String(120))
    flag = Column(String(20))
    technician_id = Column(Integer, ForeignKey("users.id"))
    result_datetime = Column(DateTime, default=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    sample_id = Column(Integer, ForeignKey("samples.id"), nullable=False)
    status = Column(String(20), default="Draft")  # Draft, Locked
    pathologist_id = Column(Integer, ForeignKey("pathologists.id"))
    verified_by = Column(Integer, ForeignKey("users.id"))
    verified_at = Column(DateTime)
    remarks = Column(String(255))


class Bill(Base):
    __tablename__ = "bills"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    receipt_number = Column(String(30), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    gross_amount = Column(Float, default=0)
    discount = Column(Float, default=0)
    net_amount = Column(Float, default=0)
    paid_amount = Column(Float, default=0)
    due_amount = Column(Float, default=0)
    payment_mode = Column(String(30))
    status = Column(String(20), default="Active")
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("tenant_id", "receipt_number", name="uq_tenant_receipt_number"),)

    patient = relationship("Patient")


class BillItem(Base):
    __tablename__ = "bill_items"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    description = Column(String(150))
    price = Column(Float, default=0)


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    amount = Column(Float, default=0)
    mode = Column(String(30))
    date = Column(DateTime, default=datetime.utcnow)


class Staff(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    staff_code = Column(String(20))
    name = Column(String(120), nullable=False)
    designation = Column(String(80))
    mobile = Column(String(20))
    joining_date = Column(Date)
    salary = Column(Float)
    status = Column(String(20), default="Active")


class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)
    date = Column(Date, default=date.today)
    status = Column(String(20))
    __table_args__ = (UniqueConstraint("tenant_id", "staff_id", "date", name="uq_tenant_staff_date"),)


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String(150), nullable=False)
    category = Column(String(80))
    unit = Column(String(30))
    current_stock = Column(Float, default=0)
    min_stock = Column(Float, default=0)


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    txn_type = Column(String(10))
    quantity = Column(Float)
    date = Column(DateTime, default=datetime.utcnow)
    notes = Column(String(255))


class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    date = Column(Date, default=date.today)
    category = Column(String(80))
    description = Column(String(255))
    amount = Column(Float, default=0)
    payment_mode = Column(String(30))
    added_by = Column(Integer, ForeignKey("users.id"))


class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    key = Column(String(60), nullable=False)
    value = Column(Text)
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_tenant_setting_key"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(150))
    record_id = Column(String(50))
    details = Column(String(255))
    timestamp = Column(DateTime, default=datetime.utcnow)
