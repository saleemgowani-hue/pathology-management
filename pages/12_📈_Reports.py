from datetime import date, timedelta
import io
import streamlit as st
import pandas as pd
from sqlalchemy import func

from utils.session import get_db, require_login, current_tenant_id
from db.models import Patient, Sample, Bill, Expense, TestItem, TestOrder, Doctor

require_login()
db = get_db()
tid = current_tenant_id()

st.title("📈 Reports")

report_choice = st.selectbox("Choose a report", [
    "Patient Report", "Sample Collection Report", "Collection Report",
    "Pending Payment Report", "Expense Report", "Test-wise Report", "Doctor-wise Report",
])

col1, col2 = st.columns(2)
start = col1.date_input("From", value=date.today() - timedelta(days=30))
end = col2.date_input("To", value=date.today())


def to_excel_bytes(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Report")
    return buf.getvalue()


if report_choice == "Patient Report":
    rows = db.query(Patient).filter(Patient.tenant_id == tid, Patient.registration_date.between(start, end)).all()
    df = pd.DataFrame([{"Patient ID": r.patient_code, "Name": r.name, "Age": r.age, "Gender": r.gender,
                         "Mobile": r.mobile, "Reg. Date": r.registration_date} for r in rows])

elif report_choice == "Sample Collection Report":
    rows = db.query(Sample).filter(Sample.tenant_id == tid, func.date(Sample.collection_datetime).between(start, end)).all()
    df = pd.DataFrame([{"Sample No": r.sample_number, "Patient": r.patient.name, "Type": r.sample_type,
                         "Status": r.status, "Collected": r.collection_datetime} for r in rows])

elif report_choice == "Collection Report":
    rows = db.query(Bill).filter(Bill.tenant_id == tid, Bill.status == "Active",
                                  func.date(Bill.created_at).between(start, end)).all()
    df = pd.DataFrame([{"Receipt": r.receipt_number, "Patient": r.patient.name, "Net": r.net_amount,
                         "Paid": r.paid_amount, "Due": r.due_amount, "Mode": r.payment_mode,
                         "Date": r.created_at} for r in rows])
    if not df.empty:
        st.metric("Total Collection", f"₹{df['Paid'].sum():,.0f}")

elif report_choice == "Pending Payment Report":
    rows = db.query(Bill).filter(Bill.tenant_id == tid, Bill.status == "Active", Bill.due_amount > 0).all()
    df = pd.DataFrame([{"Receipt": r.receipt_number, "Patient": r.patient.name, "Net": r.net_amount,
                         "Due": r.due_amount} for r in rows])

elif report_choice == "Expense Report":
    rows = db.query(Expense).filter(Expense.tenant_id == tid, Expense.date.between(start, end)).all()
    df = pd.DataFrame([{"Date": r.date, "Category": r.category, "Description": r.description,
                         "Amount": r.amount, "Mode": r.payment_mode} for r in rows])
    if not df.empty:
        st.metric("Total Expenses", f"₹{df['Amount'].sum():,.0f}")

elif report_choice == "Test-wise Report":
    q = (db.query(TestItem.name, func.count(TestOrder.id))
         .join(TestOrder, TestOrder.test_id == TestItem.id)
         .filter(TestItem.tenant_id == tid).group_by(TestItem.name)
         .order_by(func.count(TestOrder.id).desc()).all())
    df = pd.DataFrame(q, columns=["Test", "Order Count"])

elif report_choice == "Doctor-wise Report":
    docs = db.query(Doctor).filter_by(tenant_id=tid).all()
    data = []
    for d in docs:
        pcount = db.query(Patient).filter_by(tenant_id=tid, referring_doctor_id=d.id).count()
        revenue = db.query(func.sum(Bill.net_amount)).join(Patient).filter(
            Patient.referring_doctor_id == d.id, Bill.status == "Active", Bill.tenant_id == tid).scalar() or 0
        data.append({"Doctor": d.name, "Patients": pcount, "Revenue": revenue})
    df = pd.DataFrame(data)

else:
    df = pd.DataFrame()

if df.empty:
    st.info("No records found for this report / date range.")
else:
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Export to Excel", data=to_excel_bytes(df),
                        file_name=f"{report_choice.replace(' ', '_')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
