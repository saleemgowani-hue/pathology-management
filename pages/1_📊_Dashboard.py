from datetime import date, timedelta
import streamlit as st
from sqlalchemy import func

from utils.session import get_db, require_login, current_tenant_id, current_role
from utils.helpers import add_demo_patients
from db.seed_demo import reset_demo_data, DEMO_LAB_CODE
from db.models import Patient, Sample, Report, Bill, Doctor, TestItem, Staff, TestOrder, Tenant

require_login()
db = get_db()
tid = current_tenant_id()

st.title("📊 Dashboard")

_tenant = db.query(Tenant).get(tid)
if current_role() == "admin" and _tenant.lab_code == DEMO_LAB_CODE:
    with st.container(border=True):
        st.markdown("**🧪 Demo Data Controls**")
        st.caption(
            "This is the public demo lab — anything entered here resets automatically "
            "within 60 minutes. Use these to add or clear sample data on demand."
        )
        col_add, col_remove = st.columns(2)
        if col_add.button("➕ Add Demo Data", use_container_width=True):
            add_demo_patients(db, tid, count=20)
            st.success("20 demo patients added.")
            st.rerun()
        if col_remove.button("🗑️ Remove Demo Data", use_container_width=True):
            reset_demo_data(db, tid)
            st.success("Demo data cleared and reset to the 20-patient baseline.")
            st.rerun()

today = date.today()

today_patients = db.query(Patient).filter(Patient.tenant_id == tid, Patient.registration_date == today).count()
today_samples = db.query(Sample).filter(Sample.tenant_id == tid, func.date(Sample.collection_datetime) == today).count()
pending_reports = db.query(Report).filter(Report.tenant_id == tid, Report.status == "Draft").count()
locked_reports = db.query(Report).filter(Report.tenant_id == tid, Report.status == "Locked").count()

today_bills = db.query(Bill).filter(Bill.tenant_id == tid, Bill.status == "Active",
                                     func.date(Bill.created_at) == today).all()
today_billing = sum(b.net_amount for b in today_bills)
total_collection = db.query(func.sum(Bill.paid_amount)).filter(Bill.tenant_id == tid, Bill.status == "Active").scalar() or 0
pending_payments = db.query(func.sum(Bill.due_amount)).filter(Bill.tenant_id == tid, Bill.status == "Active").scalar() or 0

total_doctors = db.query(Doctor).filter(Doctor.tenant_id == tid, Doctor.active == True).count()  # noqa: E712
total_tests = db.query(TestItem).filter(TestItem.tenant_id == tid, TestItem.active == True).count()  # noqa: E712
total_staff = db.query(Staff).filter(Staff.tenant_id == tid, Staff.status == "Active").count()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Today's Patients", today_patients)
col2.metric("Today's Samples", today_samples)
col3.metric("Pending Reports", pending_reports)
col4.metric("Completed Reports", locked_reports)

col5, col6, col7, col8 = st.columns(4)
col5.metric("Today's Billing", f"₹{today_billing:,.0f}")
col6.metric("Total Collection", f"₹{total_collection:,.0f}")
col7.metric("Pending Payments", f"₹{pending_payments:,.0f}")
col8.metric("Active Staff", total_staff)

col9, col10 = st.columns(2)
col9.metric("Active Doctors", total_doctors)
col10.metric("Active Tests", total_tests)

st.divider()
st.subheader("Daily Patient Trend (last 7 days)")
trend_dates, trend_values = [], []
for i in range(6, -1, -1):
    d = today - timedelta(days=i)
    trend_dates.append(d)
    trend_values.append(db.query(Patient).filter(Patient.tenant_id == tid, Patient.registration_date == d).count())

import pandas as pd
chart_df = pd.DataFrame({"Date": pd.to_datetime(trend_dates), "Patients": trend_values}).set_index("Date")
st.line_chart(chart_df)

test_stats = (
    db.query(TestItem.name, func.count(TestOrder.id))
    .join(TestOrder, TestOrder.test_id == TestItem.id)
    .filter(TestItem.tenant_id == tid)
    .group_by(TestItem.name)
    .order_by(func.count(TestOrder.id).desc())
    .limit(8)
    .all()
)
if test_stats:
    st.subheader("Test-wise Order Volume")
    test_df = pd.DataFrame(test_stats, columns=["Test", "Orders"]).set_index("Test")
    st.bar_chart(test_df)
